"""Route B, the session file, against route A: `ingestion/session_extraction.py`.

Three things are tested here.

1. **The two routes give the same result** (P9c section 5). The same Pass 1 and
   Pass 2 JSON goes through route A, `extract_multi_year` with `_call_llm` replaced
   by a stub, and through route B, a session file read by `load_session_extraction`.
   The `FinancialStatements` and the item lists must be equal. That is the Phase 9
   constraint, and its expected value is an identity: same input, same output. The
   stub also only answers a prompt equal to the one `pass1_prompts` /
   `pass2_prompts` gives for that plan, so the prompts route A sends and the
   prompts route B prints are proved equal by the same run.

2. **The loader's stops** (P9c section 6), one test per row of the stop list in
   `.agent/assignments/P9a-session-route.md` step 10. Each asserts `ValueError` and
   that ONE line of the message names everything the step says it names: the file,
   the filing index and its PDF, and the year and key where one applies.

3. **The route label** (P9c section 7), from P9a step 11.

**Where the expected values come from.** Equality between routes is an identity.
The stop messages' contents are the names the P9a assignment requires. The few
figures asserted (years present, item count after dedupe) are worked out by hand
in a comment beside each. No value here was read off the code's output.

**No test reaches the API.** An autouse fixture replaces `_call_llm` with a function
that raises; the route A tests replace it again with a stub that answers only the
exact (system prompt, user prompt, PDF bytes) triples it was given, and raises on
anything else. `resolve_provider` is replaced too, so no test depends on what
`.env` holds (`config.py` fills from it each name the environment does not already
set, once, at import). The PDFs are written under
`tmp_path` by `tests/unit/_pass1_pdf.py`, each printing its filing's Pass 1 rows on
the pages they cite (P12a); nothing reads `10K_filings/`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    PASS1_BALANCE_SHEET_FIELDS,
    PASS1_YEAR_FIELDS,
    FilingPlan,
    ProviderResolution,
    describe_resolution,
    extract_multi_year,
    parse_pass1,
    pass1_prompts,
    pass2_prompts,
    plan_filings,
)
from ingestion.session_extraction import (
    SESSION_FORMAT,
    _compress,
    cmd_check,
    cmd_plan,
    cmd_prompt,
    load_session_extraction,
    main,
)
from tests.unit._fiscal_year_stub import stub_evidence_reader
from tests.unit._pass1_pdf import reprint_filing_pdf, write_pass1_pdf
from tests.unit._printed_lines import lines, printed_balance_sheet, printed_year

MODEL = "claude-opus-5"
TICKER = "TST"
COMPANY = "Test Co"


@pytest.fixture(autouse=True)
def _no_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the API boundary for every test in this file."""

    def _refuse(*args: object, **kwargs: object) -> tuple[str, int, int]:
        raise AssertionError("a session-route test reached _call_llm")

    monkeypatch.setattr(ce, "_call_llm", _refuse)


# ===========================================================================
# Builders. Hand-written JSON, every year reconciling.
# ===========================================================================
#
# One year is the base below times an integer k. Every Pass 1 check is linear, so a
# year that reconciles at k = 1 reconciles at every k:
#   gross  600 = 1000 - 400
#   EBIT   300 = 600 - 150 - 100 - 50
#   NI     228 = 300 + 10 - 20 + (-5) - 57

_BASE_YEAR: dict[str, float] = {
    "revenue": 1000, "cost_of_revenue": 400, "gross_profit": 600, "sga": 150,
    "rd_expense": 100, "depreciation_amortization": 30, "other_operating_expense": 50,
    "operating_income": 300, "interest_expense": 20, "interest_income": 10,
    "other_non_operating": -5, "tax_expense": 57, "net_income": 228,
    "diluted_shares": 48, "cfo": 290, "capex": 70, "sbc": 25,
    "change_in_working_capital": -15,
}


def year_entry(year: int, k: int = 1) -> dict[str, Any]:
    # P11a shape: each field one printed row, holding the base value times k.
    return printed_year(year, {key: [value * k] for key, value in _BASE_YEAR.items()})


def balance_sheet(year: int) -> dict[str, Any]:
    # assets 860 = liabilities 575 + equity 285 (see test_claude_extractor.py).
    # P11a: the printed totals are those two sums, "Total assets 860" and
    # "Total liabilities and equity 860"; the check compares them with the rows.
    return printed_balance_sheet(year, {
        "cash": [100], "short_term_investments": [50],
        "accounts_receivable": [80], "inventory": [60], "other_current_assets": [10],
        "ppe_net": [300], "goodwill": [200], "intangible_assets": [40],
        "other_non_current_assets": [20], "accounts_payable": [70],
        "accrued_liabilities": [30], "other_current_liabilities": [15],
        "short_term_debt": [25], "long_term_debt": [400],
        "other_non_current_liabilities": [35], "total_equity": [285],
        # The two NCI memo lines (P10a): [] (was an explicit 0 before P11a),
        # this company prints none. Required by the loader; never added to any total.
        "noncontrolling_interest_nonredeemable": [],
        "noncontrolling_interest_redeemable": [],
        "total_assets": [860], "total_liabilities_and_equity": [860],
    })


def pass1(years: list[dict[str, Any]], bs: dict[str, Any]) -> dict[str, Any]:
    return {"ticker": TICKER, "company_name": COMPANY, "currency": "USD",
            "units": "Millions", "historical_years": years, "latest_balance_sheet": bs}


def nri(year: int, amount: float, description: str, **overrides: Any) -> dict[str, Any]:
    item = {"year": year, "description": description, "amount": amount,
            "line_item": "sga", "direction": "add_back", "category": "restructuring",
            "confidence": "high", "source": "Note 8"}
    item.update(overrides)
    return item


def make_pdf(directory: Path, fiscal_year: int, p1: dict[str, Any] | None = None) -> Path:
    """A real PDF for one filing, printing every row of `p1` on the page it cites.

    Since P12a both routes look each printed line up on its cited page, so the
    stand-in bytes this used to write would stop every run. The pages are built
    from the filing's own Pass 1 (`tests/unit/_pass1_pdf.py`), which is why each
    builder below writes its Pass 1 first and its PDF second. The cover names the
    fiscal year, so each filing's bytes differ. With no `p1` (the `plan` test, whose
    year reader is stubbed) the PDF is the cover alone.
    """
    path = directory / f"{TICKER}_10-K_{fiscal_year}.pdf"
    write_pass1_pdf(path, p1, cover=f"Test filing for fiscal {fiscal_year}")
    return path.resolve()


def filing(pdf: Path, fiscal_year: int, target_years: list[int] | None, include_bs: bool,
           p1: dict[str, Any] | None, p2: dict[str, Any] | None) -> dict[str, Any]:
    data = pdf.read_bytes()
    return {
        "fiscal_year": fiscal_year,
        "pdf_path": str(pdf),
        # hashlib directly, not fingerprint_filings: the test's own record of the bytes.
        "pdf_sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "target_years": target_years,
        "include_bs": include_bs,
        "pages_read": {"pass1": [10, 11, 12], "pass2": [40, 41]},
        "pass1": p1,
        "pass2": p2,
    }


def session(filings: list[dict[str, Any]], model: Any = MODEL) -> dict[str, Any]:
    return {
        "format": SESSION_FORMAT,
        "ticker": TICKER,
        "company_name": COMPANY,
        "extracted_by": {"model": model, "tool": "Claude Code", "date": "2026-10-02"},
        "filings": filings,
    }


def write(directory: Path, data: dict[str, Any], name: str = "session.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- one filing ------------------------------------------------------------
#
# Plan, from the routing table (docs/3-architecture/extraction.md): one filing ->
# every year, and the balance sheet. Pass 1 gives 2023 (k=1) and 2024 (k=2).

def one_filing(directory: Path) -> dict[str, Any]:
    p1 = pass1([year_entry(2023, 1), year_entry(2024, 2)], balance_sheet(2024))
    pdf = make_pdf(directory, 2024, p1)
    p2 = {"non_recurring_items": [
        nri(2024, 12.0, "Plant closure"),
        nri(2023, 3.0, "Legal settlement", category="litigation", source=""),
    ]}
    return session([filing(pdf, 2024, None, True, p1, p2)])


# --- three filings -----------------------------------------------------------
#
# Plan, from the routing table: 2022 oldest -> every year, no B/S; 2023 middle ->
# [2023], no B/S; 2024 newest -> [2024], with B/S.
#
#   2022 10-K: years 2020, 2021, 2022; items A (2022, 5, add_back) and B (2021, 2)
#   2023 10-K: year 2023;              items A again (same key) and C (2023, 7, low)
#   2024 10-K: year 2024 + B/S 2024;   item  D (2024, 9, source "")
#
# Expected after the merge, by hand: years [2020, 2021, 2022, 2023, 2024]; one
# balance sheet, 2024; items A, B, C, D, in that order: 5 in, A's duplicate dropped.

def three_filings(directory: Path) -> dict[str, Any]:
    p1s = {
        2022: pass1([year_entry(2020, 1), year_entry(2021, 2), year_entry(2022, 3)], {}),
        2023: pass1([year_entry(2023, 4)], {}),
        2024: pass1([year_entry(2024, 5)], balance_sheet(2024)),
    }
    pdfs = {y: make_pdf(directory, y, p1s[y]) for y in (2022, 2023, 2024)}
    item_a = nri(2022, 5.0, "Restructuring A")
    return session([
        filing(pdfs[2022], 2022, None, False, p1s[2022],
               {"non_recurring_items": [item_a, nri(2021, 2.0, "Impairment B",
                                                    category="impairment")]}),
        filing(pdfs[2023], 2023, [2023], False, p1s[2023],
               {"non_recurring_items": [dict(item_a, description="A, read again"),
                                        nri(2023, 7.0, "Settlement C", confidence="low")]}),
        filing(pdfs[2024], 2024, [2024], True, p1s[2024],
               {"non_recurring_items": [nri(2024, 9.0, "Severance D", source="")]}),
    ])


# ===========================================================================
# Route A, through a stub that only answers what it was given
# ===========================================================================

_RESOLUTION = ProviderResolution(
    provider="claude", model=MODEL, transport="anthropic-direct",
    transport_label="stub", credential="anthropic-api-key",
    credential_source="stub: no call is made",
)


def run_route_a(monkeypatch: pytest.MonkeyPatch, data: dict[str, Any],
                filings_order: list[int]) -> tuple[Any, Any, list[tuple[str, str]]]:
    """Feed the session file's own JSON through extract_multi_year.

    The answer table is keyed on (system prompt, user prompt, PDF bytes), built from
    `pass1_prompts` / `pass2_prompts` for each filing's plan. A call route A makes
    with any other prompt or PDF raises, so equality of results also proves the
    prompts route A sends are the prompts route B prints.
    """
    answers: dict[tuple[str, str, bytes], str] = {}
    for entry in data["filings"]:
        plan = FilingPlan(
            fiscal_year=entry["fiscal_year"], pdf_path=entry["pdf_path"],
            target_years=None if entry["target_years"] is None else tuple(entry["target_years"]),
            include_bs=entry["include_bs"],
        )
        pdf_bytes = Path(entry["pdf_path"]).read_bytes()
        p1_json = json.dumps(entry["pass1"])
        answers[(*pass1_prompts(plan), pdf_bytes)] = p1_json
        own_fin, _ = parse_pass1(p1_json, TICKER, COMPANY)
        answers[(*pass2_prompts(plan, own_fin), pdf_bytes)] = json.dumps(entry["pass2"])

    calls: list[tuple[str, str]] = []

    def stub(system_prompt: str, user_prompt: str, resolution: ProviderResolution,
             pdf_bytes: bytes | None = None) -> tuple[str, int, int]:
        key = (system_prompt, user_prompt, pdf_bytes or b"")
        if key not in answers:
            raise AssertionError(
                f"route A sent a call the stub was not given: {user_prompt[:120]!r}",
            )
        calls.append((system_prompt, user_prompt))
        return answers[key], 0, 0

    def resolve(provider: str, model: str | None) -> ProviderResolution:
        return _RESOLUTION

    monkeypatch.setattr(ce, "_call_llm", stub)
    monkeypatch.setattr(ce, "resolve_provider", resolve)

    by_year = {e["fiscal_year"]: e["pdf_path"] for e in data["filings"]}
    fin, items = extract_multi_year(
        filings=[(y, by_year[y]) for y in filings_order],
        ticker=TICKER, company_name=COMPANY, provider="claude",
    )
    return fin, items, calls


# ===========================================================================
# 5. The two routes give the same result
# ===========================================================================

def test_one_filing_both_routes_give_equal_statements_and_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = one_filing(tmp_path)
    route_b = load_session_extraction(write(tmp_path, data))
    fin_a, items_a, calls = run_route_a(monkeypatch, data, [2024])

    # Identity: same JSON in, same statements and items out.
    assert route_b.financials == fin_a
    assert route_b.non_recurring == items_a
    # Route A made exactly Pass 1 and Pass 2 for the one filing (no retry).
    assert len(calls) == 2
    # By hand: years 2023 and 2024 from the one filing, its B/S 2024, two items.
    assert route_b.financials.years == [2023, 2024]
    assert [b.year for b in route_b.financials.balance_sheets] == [2024]
    assert [i.description for i in route_b.non_recurring] == [
        "Plant closure", "Legal settlement"]
    assert route_b.validation_errors == []


def test_three_filings_both_routes_give_equal_statements_and_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = three_filings(tmp_path)
    route_b = load_session_extraction(write(tmp_path, data))
    # Route A is given the filings out of order; plan_filings sorts them.
    fin_a, items_a, calls = run_route_a(monkeypatch, data, [2024, 2022, 2023])

    assert route_b.financials == fin_a
    assert route_b.non_recurring == items_a
    # Two calls per filing, three filings, no retry: 6.
    assert len(calls) == 6
    # By hand (comment above three_filings).
    assert route_b.financials.years == [2020, 2021, 2022, 2023, 2024]
    assert [b.year for b in route_b.financials.balance_sheets] == [2024]
    assert [i.description for i in route_b.non_recurring] == [
        "Restructuring A", "Impairment B", "Settlement C", "Severance D"]
    # Revenue = 1000 * k, where k is the year's multiplier in three_filings.
    assert [s.revenue for s in route_b.financials.income_statements] == [
        1000.0, 2000.0, 3000.0, 4000.0, 5000.0]


def test_a_changed_figure_makes_the_routes_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: the equality above is not vacuous.

    Route B's file has one figure changed after route A's answers were built from
    the original; the two must then differ.
    """
    data = one_filing(tmp_path)
    fin_a, _, _ = run_route_a(monkeypatch, data, [2024])
    # sbc is one printed row (P11a shape); its value was 25 * 2 = 50.
    data["filings"][0]["pass1"]["historical_years"][1]["sbc"][0]["value"] = 51
    # The filing now prints 51 (P12a), so the page check passes and the only
    # difference between the routes is the figure.
    reprint_filing_pdf(data["filings"][0])
    route_b = load_session_extraction(write(tmp_path, data))
    assert route_b.financials != fin_a


# ===========================================================================
# 6. The loader's stops — P9a step 10, one test per row
# ===========================================================================

def stop_message(path: Path) -> str:
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    return str(excinfo.value)


def assert_one_line_names(message: str, *parts: str) -> None:
    """Some single line of the message holds every part: the file, the filing,
    the PDF, the year, the key. A message that names them on different lines would
    not tell the reader which year the key belongs to."""
    lines = message.splitlines()
    assert any(all(part in line for part in parts) for line in lines), (
        f"no line names all of {parts!r}:\n{message}"
    )


def pdf_name(fiscal_year: int) -> str:
    return f"{TICKER}_10-K_{fiscal_year}.pdf"


# --- row 1: format ---------------------------------------------------------

@pytest.mark.parametrize("value", ["session-extraction-v0", None])
def test_stop_wrong_format(tmp_path: Path, value: Any) -> None:
    data = one_filing(tmp_path) | {"format": value}
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "format")


def test_stop_absent_format(tmp_path: Path) -> None:
    data = one_filing(tmp_path)
    del data["format"]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "'format'")


# --- row 2: extracted_by.model missing or empty ------------------------------

@pytest.mark.parametrize("model", [None, "", "   "])
def test_stop_model_empty(tmp_path: Path, model: Any) -> None:
    path = write(tmp_path, session(one_filing(tmp_path)["filings"], model=model))
    assert_one_line_names(stop_message(path), str(path.resolve()), "extracted_by.model")


def test_stop_model_absent(tmp_path: Path) -> None:
    data = one_filing(tmp_path)
    del data["extracted_by"]["model"]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "extracted_by.model")


# --- row 3: pass1 or pass2 null ----------------------------------------------

@pytest.mark.parametrize("which", ["pass1", "pass2"])
def test_stop_pass_is_null(tmp_path: Path, which: str) -> None:
    data = three_filings(tmp_path)
    data["filings"][1][which] = None
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), f"'{which}' is null")


# --- row 4: the PDF missing, or changed --------------------------------------

def test_stop_pdf_missing(tmp_path: Path) -> None:
    data = three_filings(tmp_path)
    path = write(tmp_path, data)
    (tmp_path / pdf_name(2024)).unlink()
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[2]",
                          pdf_name(2024), "not on disk")


def test_stop_pdf_changed(tmp_path: Path) -> None:
    data = three_filings(tmp_path)
    path = write(tmp_path, data)
    with (tmp_path / pdf_name(2023)).open("ab") as handle:
        handle.write(b"x")  # one byte appended after the session hashed it
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), "has changed")


# --- row 5: any schema key absent --------------------------------------------
#
# The key lists, written out from the Pass 1 schema (P9a step 10 names it as the
# source; docs/3-architecture/extraction.md shows the same schema). They are written
# here by hand rather than read from the code, then checked against the exported
# tuples, so a key dropped from the schema shows up as a failure, not a shorter loop.

YEAR_KEYS = (
    "year", "revenue", "cost_of_revenue", "gross_profit", "sga", "rd_expense",
    "depreciation_amortization", "other_operating_expense", "operating_income",
    "interest_expense", "interest_income", "other_non_operating", "tax_expense",
    "net_income", "diluted_shares", "cfo", "capex", "sbc", "change_in_working_capital",
)
BALANCE_SHEET_KEYS = (
    "year", "cash", "short_term_investments", "accounts_receivable", "inventory",
    "other_current_assets", "ppe_net", "goodwill", "intangible_assets",
    "other_non_current_assets", "accounts_payable", "accrued_liabilities",
    "other_current_liabilities", "short_term_debt", "long_term_debt",
    "other_non_current_liabilities", "total_equity",
    "noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable",
    # P11a: the two printed totals, read only to check the reading
    # (.agent/assignments/P11a-printed-lines.md, "Two new printed totals").
    "total_assets", "total_liabilities_and_equity",
)


def test_the_required_key_lists_are_the_schema() -> None:
    # 19 keys per year and 21 in the balance sheet, as written in the schema
    # (17 until P10a added the two printed NCI lines, 19 until P11a added the two
    # printed totals; ingestion/claude_extractor.py:_FINANCIALS_BALANCE_SHEET_SCHEMA).
    assert PASS1_YEAR_FIELDS == YEAR_KEYS
    assert PASS1_BALANCE_SHEET_FIELDS == BALANCE_SHEET_KEYS


@pytest.mark.parametrize("key", [k for k in YEAR_KEYS if k != "year"])
def test_stop_year_key_absent(tmp_path: Path, key: str) -> None:
    data = one_filing(tmp_path)
    del data["filings"][0]["pass1"]["historical_years"][0][key]  # the 2023 entry
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "year 2023", f"'{key}'", "absent")


def test_stop_year_key_year_absent(tmp_path: Path) -> None:
    # With 'year' itself gone the entry cannot be named by its year, so it is
    # named by its position: historical_years[1].
    data = one_filing(tmp_path)
    del data["filings"][0]["pass1"]["historical_years"][1]["year"]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "historical_years[1]", "'year'", "absent")


@pytest.mark.parametrize("key", [k for k in BALANCE_SHEET_KEYS if k != "year"])
def test_stop_balance_sheet_key_absent(tmp_path: Path, key: str) -> None:
    data = three_filings(tmp_path)
    del data["filings"][2]["pass1"]["latest_balance_sheet"][key]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[2]",
                          pdf_name(2024), "balance sheet 2024", f"'{key}'", "absent")


@pytest.mark.parametrize("bad", [None, "12", True, float("nan"), float("inf")])
def test_stop_year_key_not_a_finite_number(tmp_path: Path, bad: Any) -> None:
    # A null is an absent value with a key; a string, a bool or a NaN is not a
    # figure. json writes nan/inf as NaN/Infinity and reads them back.
    # P11a: the figure is the `value` of a printed row, so the bad value goes
    # there, and the line names the row's index too ("line 0").
    data = one_filing(tmp_path)
    data["filings"][0]["pass1"]["historical_years"][0]["revenue"][0]["value"] = bad
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "year 2023", "'revenue'", "line 0", "'value'")


@pytest.mark.parametrize("bad", [None, "12", 1000], ids=["null", "string", "bare number"])
def test_stop_year_key_not_a_list_of_printed_lines(tmp_path: Path, bad: Any) -> None:
    # The field itself, not a row of it: a null, a string, or a bare number (the
    # old v1 shape) is not a list of printed lines (P11a step 4).
    data = one_filing(tmp_path)
    data["filings"][0]["pass1"]["historical_years"][0]["revenue"] = bad
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "year 2023", "'revenue'", "must be a list")


def test_explicit_zero_is_accepted(tmp_path: Path) -> None:
    """A stop on absence must not become a stop on zero (P9c section 6).

    sbc is outside every arithmetic check, and inventory is a balance sheet line
    a services company reports as nothing, so 0 is a legitimate reading of both.

    P11a: "the filing prints no such row" is now the empty list `[]`, not an
    explicit 0, and the printed totals are checked against the rows. A filing
    with no inventory row prints totals that do not include one, so the sheet is
    rebuilt to balance without it, by hand:
      assets = 860 - 60 (inventory)                       = 800
      equity = 285 - 60                                    = 225
      L + E  = 575 + 225                                   = 800
    and the printed totals are 800 and 800.
    """
    data = one_filing(tmp_path)
    data["filings"][0]["pass1"]["historical_years"][0]["sbc"] = []
    balance = data["filings"][0]["pass1"]["latest_balance_sheet"]
    balance["inventory"] = []
    balance |= {
        "total_equity": lines("total_equity", [225], balance_sheet=True),
        "total_assets": lines("total_assets", [800], balance_sheet=True),
        "total_liabilities_and_equity": lines(
            "total_liabilities_and_equity", [800], balance_sheet=True),
    }
    # The filing prints the rebuilt sheet (P12a: each row is looked up on its page).
    reprint_filing_pdf(data["filings"][0])
    loaded = load_session_extraction(write(tmp_path, data))
    # The value is the explicit input, 0, not a default.
    assert loaded.financials.get_cash_flow(2023).stock_based_compensation == 0.0
    assert loaded.financials.get_balance_sheet(2024).inventory == 0.0
    assert loaded.validation_errors == []


# --- row 6: target_years set, and pass1's years differ -------------------------

def test_stop_pass1_years_differ_from_the_plan(tmp_path: Path) -> None:
    # The plan asks the 2023 10-K for [2023]; pass1 gives 2022.
    data = three_filings(tmp_path)
    data["filings"][1]["pass1"]["historical_years"][0]["year"] = 2022
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), "[2023]", "[2022]")


def test_stop_target_years_edited_by_hand(tmp_path: Path) -> None:
    # The file's own plan must equal plan_filings'; a hand edit stops.
    data = three_filings(tmp_path)
    data["filings"][1]["target_years"] = [2023, 2022]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), "'target_years'")


# --- row 7: include_bs against latest_balance_sheet ----------------------------

def test_stop_balance_sheet_planned_but_empty(tmp_path: Path) -> None:
    data = one_filing(tmp_path)
    data["filings"][0]["pass1"]["latest_balance_sheet"] = {}
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "latest_balance_sheet", "empty")


def test_stop_balance_sheet_planned_without_a_year(tmp_path: Path) -> None:
    data = one_filing(tmp_path)
    del data["filings"][0]["pass1"]["latest_balance_sheet"]["year"]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "balance sheet", "'year'")


def test_stop_balance_sheet_where_the_plan_has_none(tmp_path: Path) -> None:
    # The 2022 10-K is the oldest of three: the plan takes no B/S from it.
    data = three_filings(tmp_path)
    data["filings"][0]["pass1"]["latest_balance_sheet"] = balance_sheet(2022)
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2022), "latest_balance_sheet", "{}")


# --- Pass 2 items: route A's stops, carried through the loader ----------------

@pytest.mark.parametrize("key", ["confidence", "source"])
def test_stop_pass2_item_key_absent(tmp_path: Path, key: str) -> None:
    data = three_filings(tmp_path)
    del data["filings"][1]["pass2"]["non_recurring_items"][1][key]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), f"'{key}'", "year 2023", "Settlement C")



@pytest.mark.parametrize(
    "key", ["year", "description", "amount", "line_item", "direction", "category"],
)
def test_stop_pass2_item_other_key_absent(tmp_path: Path, key: str) -> None:
    # Written by P9c, when route A's parser was the only check and its KeyError
    # named the key but not the item. Since P9d the loader checks the key itself
    # before the parser runs; the stronger test, naming the item as well, is
    # test_stop_pass2_item_missing_a_schema_key below, over all eight keys.
    data = three_filings(tmp_path)
    del data["filings"][1]["pass2"]["non_recurring_items"][1][key]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[1]",
                          pdf_name(2023), f"'{key}'")


# --- Pass 2 shape, checked by the loader itself (P9d-pass2-checks) ------------
#
# The first three tests were written red by the P9c tester in
# tests/unit/test_session_extraction_rule3_red.py and went green at 33afced. They
# are moved here unchanged in what they assert, so the gate runs them.
#
# The rest lock the stops P9d added that only scratch probes had shown. Each one
# breaks item 1 of one_filing: nri(2023, 3.0, "Legal settlement"). Item 1 rather
# than item 0 because its year, 2023, is not in the PDF's name (TST_10-K_2024.pdf),
# so "year 2023" on the line can only have come from the item; and its index, 1,
# is not the 0 of filings[0]. Every expected part is a name the P9d assignment
# requires ("the file, the filing index, the PDF name and, for an item, its year
# and description"), spelled from the builder above, not from a run.

ITEM = "non_recurring_items[1]"
ITEM_YEAR = "year 2023"          # nri(2023, ...) in one_filing
ITEM_DESCRIPTION = "Legal settlement"

# The eight keys of a Pass 2 item, written out from the Pass 2 schema
# (_NRI_SCHEMA in ingestion/claude_extractor.py, the dict the Pass 2 prompt is
# built from; docs/3-architecture/extraction.md shows it too). Written here by hand,
# then checked against nri() above, so a key the builder stops writing shows up.
PASS2_ITEM_KEYS = ("year", "description", "amount", "line_item", "direction",
                   "category", "confidence", "source")


@pytest.mark.parametrize("not_a_list", [{"a": 1}, "restructuring"])
def test_pass2_items_not_a_list_stops_naming_file_and_filing(
    tmp_path: Path, not_a_list: Any,
) -> None:
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"] = {"non_recurring_items": not_a_list}
    path = write(tmp_path, data)
    # Before P9d: AttributeError: 'str' object has no attribute 'get'.
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    assert_one_line_names(str(excinfo.value), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "non_recurring_items")


def test_pass2_item_amount_nan_stops_naming_filing_year_and_description(
    tmp_path: Path,
) -> None:
    data = one_filing(tmp_path)
    # json.dumps writes float('nan') as NaN, and json.loads reads it back.
    data["filings"][0]["pass2"]["non_recurring_items"][0]["amount"] = float("nan")
    path = write(tmp_path, data)
    # Before P9d: loaded, with amount=nan.
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    assert_one_line_names(str(excinfo.value), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "2024", "Plant closure")


def test_the_pass2_item_builder_writes_every_schema_key(tmp_path: Path) -> None:
    # Guards the parametrisation below: the hand-written list is the schema's eight
    # keys, and nri() writes all eight, so no case deletes a key that was never there.
    assert tuple(ce._NRI_SCHEMA["non_recurring_items"][0]) == PASS2_ITEM_KEYS
    item = one_filing(tmp_path)["filings"][0]["pass2"]["non_recurring_items"][1]
    assert tuple(item) == PASS2_ITEM_KEYS
    assert (item["year"], item["description"]) == (2023, ITEM_DESCRIPTION)


@pytest.mark.parametrize("key", PASS2_ITEM_KEYS)
def test_stop_pass2_item_missing_a_schema_key(tmp_path: Path, key: str) -> None:
    data = one_filing(tmp_path)
    del data["filings"][0]["pass2"]["non_recurring_items"][1][key]
    path = write(tmp_path, data)
    # The item is named by its index always, and by its year and its description
    # unless that is the key removed (P9d assignment step 1, last bullet).
    item_names = [ITEM]
    if key != "year":
        item_names.append(ITEM_YEAR)
    if key != "description":
        item_names.append(ITEM_DESCRIPTION)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), *item_names, f"'{key}'", "absent")


@pytest.mark.parametrize(
    "bad",
    # A string that would convert to 12.0, a bool Python counts as 1, a null, and
    # an infinity json writes as Infinity and reads back. None of them is a finite
    # JSON number; Pass 1 refuses the same four (test_stop_year_key_not_a_finite_number).
    ["12", True, None, float("inf")],
    ids=["string", "bool", "null", "inf"],
)
def test_stop_pass2_item_amount_not_a_finite_json_number(
    tmp_path: Path, bad: Any,
) -> None:
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"]["non_recurring_items"][1]["amount"] = bad
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), ITEM, ITEM_YEAR, ITEM_DESCRIPTION,
                          "'amount'")


@pytest.mark.parametrize("bad", [2025.5, True], ids=["fraction", "bool"])
def test_stop_pass2_item_year_not_an_integer(tmp_path: Path, bad: Any) -> None:
    # int() would turn 2025.5 into 2025 and True into 1, silently. The year is the
    # bad value here, so the item is named by its index and its description.
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"]["non_recurring_items"][1]["year"] = bad
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), ITEM, ITEM_DESCRIPTION, "'year'")


def test_stop_pass2_item_not_an_object(tmp_path: Path) -> None:
    # A string has no year and no description, so its index is the only name it has.
    # "JSON object" says what it should have been, as the "filing not an object" row
    # of _SHAPE_STOPS does. Without it, a string item reported as "key 'year' is
    # absent" eight times would also pass: `"year" in "restructuring"` is a
    # substring test, not a key lookup.
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"]["non_recurring_items"][1] = "restructuring"
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), ITEM, "JSON object")


def test_stop_pass2_items_absent(tmp_path: Path) -> None:
    # The one Pass 2 absence P9d leaves to route A's parser (its shape check returns
    # no problem and lets the parser say why absent and [] differ). Rule 3 still
    # asks: does it stop, and does one line name the file, the filing and the key?
    data = one_filing(tmp_path)
    del data["filings"][0]["pass2"]["non_recurring_items"]
    path = write(tmp_path, data)
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "'non_recurring_items'")


def test_pass2_item_amount_zero_loads(tmp_path: Path) -> None:
    """A stop on a bad amount must not become a stop on zero.

    0 is a finite JSON number; the item is a legitimate reading of a note that
    reports a nil charge. By hand: the two items of one_filing, in order, with
    item 1's amount the explicit 0 written below.
    """
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"]["non_recurring_items"][1]["amount"] = 0
    loaded = load_session_extraction(write(tmp_path, data))
    assert [(i.description, i.amount) for i in loaded.non_recurring] == [
        ("Plant closure", 12.0), ("Legal settlement", 0.0)]
    assert loaded.validation_errors == []


def test_every_problem_is_listed_in_one_stop(tmp_path: Path) -> None:
    # A session sets the model last, so a null model must not hide Pass 1 problems:
    # both appear in one message (P9a entry, "collected, then raised as one").
    data = one_filing(tmp_path)
    data["extracted_by"]["model"] = None
    del data["filings"][0]["pass1"]["historical_years"][0]["capex"]
    message = stop_message(write(tmp_path, data))
    assert_one_line_names(message, "extracted_by.model")
    assert_one_line_names(message, "filings[0]", "year 2023", "'capex'")


# ===========================================================================
# 7. The route label
# ===========================================================================

def test_session_label_names_the_session_route_and_the_declared_model(
    tmp_path: Path,
) -> None:
    path = write(tmp_path, one_filing(tmp_path))
    resolution = load_session_extraction(path).resolution
    # P9a step 11: provider "claude", the declared model, transport and credential
    # "claude-code-session".
    assert resolution.provider == "claude"
    assert resolution.model == MODEL
    assert resolution.transport == "claude-code-session"
    assert resolution.credential == "claude-code-session"
    # The label names the session file, and says no API call was made.
    assert str(path.resolve()) in resolution.transport_label
    assert "no API call" in resolution.credential_source
    line = describe_resolution(resolution)
    assert "Claude Code session" in line
    assert MODEL in line


# ===========================================================================
# The subcommands that need no PDF text layer: plan, prompt, check
# ===========================================================================

def test_check_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # P9a step 9: exit 0 clean, 1 when only arithmetic errors remain, 2 on a stop.
    data = one_filing(tmp_path)
    assert cmd_check(write(tmp_path, data, "clean.json")) == 0

    # 2024 gross profit 1300 against 2000 - 800 = 1200 (k = 2): 100 / 1300 = 7.7%.
    data["filings"][0]["pass1"]["historical_years"][1]["gross_profit"] = lines(
        "gross_profit", [1300])
    # The filing prints 1,300 (P12a), so the arithmetic check is the only failure.
    reprint_filing_pdf(data["filings"][0])
    assert cmd_check(write(tmp_path, data, "arith.json")) == 1

    del data["filings"][0]["pass1"]["historical_years"][1]["sbc"]
    assert cmd_check(write(tmp_path, data, "stop.json")) == 2
    assert "'sbc'" in capsys.readouterr().out


def test_plan_writes_route_a_plan_and_refuses_to_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdfs = {y: make_pdf(tmp_path, y) for y in (2022, 2023, 2024)}
    # The stand-in bytes are not a filing, so the P10c evidence reader is stubbed
    # to give each file the year a real 10-K for it would print. The verification
    # itself still runs (tests/unit/_fiscal_year_stub.py).
    asked = stub_evidence_reader(
        monkeypatch, {pdfs[y].name: y for y in (2022, 2023, 2024)})
    out = tmp_path / "skeleton.json"
    args = [f"{y}:{p}" for y, p in sorted(pdfs.items(), reverse=True)]
    assert cmd_plan(args, "tst", "Test Co", out, force=False) == 0
    assert sorted(asked) == sorted(p.name for p in pdfs.values())

    data = json.loads(out.read_text(encoding="utf-8"))
    # The routing table, in plan order; the ticker upper-cased; nothing filled in.
    assert data["ticker"] == "TST"
    assert data["extracted_by"]["model"] is None
    assert [(f["fiscal_year"], f["target_years"], f["include_bs"])
            for f in data["filings"]] == [
        (2022, None, False), (2023, [2023], False), (2024, [2024], True)]
    assert all(f["pass1"] is None and f["pass2"] is None for f in data["filings"])
    # The hash is of the bytes on disk (hashlib, independently).
    assert data["filings"][2]["pdf_sha256"] == hashlib.sha256(
        pdfs[2024].read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="already exists"):
        cmd_plan(args, "TST", "Test Co", out, force=False)


def test_prompt_prints_route_a_prompts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    data = three_filings(tmp_path)
    path = write(tmp_path, data)
    plans = plan_filings([(f["fiscal_year"], f["pdf_path"]) for f in data["filings"]])

    assert cmd_prompt(path, 1, 1) == 0
    out = capsys.readouterr().out
    system, user = pass1_prompts(plans[1])
    assert system in out
    assert user in out

    assert cmd_prompt(path, 1, 2) == 0
    out = capsys.readouterr().out
    own, _ = parse_pass1(json.dumps(data["filings"][1]["pass1"]), TICKER, COMPANY)
    system, user = pass2_prompts(plans[1], own)
    assert system in out
    assert user in out


def test_prompt_pass2_stops_before_pass1_is_written(tmp_path: Path) -> None:
    data = three_filings(tmp_path)
    data["filings"][1]["pass1"] = None
    path = write(tmp_path, data)
    with pytest.raises(ValueError, match="Pass 1 must be complete") as excinfo:
        cmd_prompt(path, 1, 2)
    assert "filings[1]" in str(excinfo.value)


# ===========================================================================
# 6b. The shape stops: every other value the loader reads, removed or malformed
# ===========================================================================
#
# P9a step 10 lists the stops the assignment required (above). The loader reads
# more than those: the identity keys, the plan keys, the hash, the page locator,
# and the type of every container. Rule 3 asks the same question of each: if it
# were missing, would the run stop and name it? One row per value, and each row
# says what one line of the message must name. The expected parts are the file,
# the filing index and PDF where one exists, and the key, as P9a step 10 requires.

_DEL = object()  # marker: delete the key instead of setting it

# (id, which session, path to the value, new value or _DEL, filing index or None,
#  fiscal year of that filing's PDF or None, the other parts the line must name)
_SHAPE_STOPS: list[tuple[str, str, tuple[Any, ...], Any, int | None, int | None,
                         tuple[str, ...]]] = [
    ("ticker absent", "one", ("ticker",), _DEL, None, None, ("'ticker'",)),
    ("ticker empty", "one", ("ticker",), " ", None, None, ("'ticker'",)),
    ("company_name absent", "one", ("company_name",), _DEL, None, None,
     ("'company_name'",)),
    ("company_name not a string", "one", ("company_name",), None, None, None,
     ("'company_name'",)),
    ("extracted_by absent", "one", ("extracted_by",), _DEL, None, None,
     ("'extracted_by'",)),
    ("extracted_by not an object", "one", ("extracted_by",), "Claude", None, None,
     ("'extracted_by'",)),
    ("filings absent", "one", ("filings",), _DEL, None, None, ("'filings'",)),
    ("filings empty", "one", ("filings",), [], None, None, ("'filings'",)),
    ("filing not an object", "three", ("filings", 0), "x", 0, None, ("JSON object",)),
    ("fiscal_year absent", "one", ("filings", 0, "fiscal_year"), _DEL, 0, 2024,
     ("'fiscal_year'",)),
    ("fiscal_year not an int", "one", ("filings", 0, "fiscal_year"), "2024", 0, 2024,
     ("'fiscal_year'",)),
    ("fiscal_year 0 among several", "three", ("filings", 0, "fiscal_year"), 0, 0, 2022,
     ("'fiscal_year'",)),
    ("pdf_path absent", "one", ("filings", 0, "pdf_path"), _DEL, 0, None,
     ("'pdf_path'",)),
    ("pdf_path empty", "one", ("filings", 0, "pdf_path"), "", 0, None, ("'pdf_path'",)),
    ("target_years absent", "one", ("filings", 0, "target_years"), _DEL, 0, 2024,
     ("'target_years'",)),
    ("target_years not a list", "three", ("filings", 1, "target_years"), "2023", 1, 2023,
     ("'target_years'",)),
    ("include_bs absent", "one", ("filings", 0, "include_bs"), _DEL, 0, 2024,
     ("'include_bs'",)),
    ("include_bs not a bool", "three", ("filings", 2, "include_bs"), "yes", 2, 2024,
     ("'include_bs'",)),
    ("include_bs edited by hand", "three", ("filings", 0, "include_bs"), True, 0, 2022,
     ("'include_bs'",)),
    ("pdf_sha256 absent", "one", ("filings", 0, "pdf_sha256"), _DEL, 0, 2024,
     ("'pdf_sha256'",)),
    ("pdf_sha256 not a string", "one", ("filings", 0, "pdf_sha256"), 123, 0, 2024,
     ("'pdf_sha256'",)),
    ("size_bytes absent", "one", ("filings", 0, "size_bytes"), _DEL, 0, 2024,
     ("'size_bytes'",)),
    ("size_bytes not an int", "one", ("filings", 0, "size_bytes"), "12", 0, 2024,
     ("'size_bytes'",)),
    ("pass1 key absent", "one", ("filings", 0, "pass1"), _DEL, 0, 2024, ("'pass1'",)),
    ("pass2 key absent", "one", ("filings", 0, "pass2"), _DEL, 0, 2024, ("'pass2'",)),
    ("pass1 not an object", "one", ("filings", 0, "pass1"), [], 0, 2024, ("'pass1'",)),
    ("pass2 not an object", "one", ("filings", 0, "pass2"), [], 0, 2024, ("'pass2'",)),
    ("pages_read absent", "one", ("filings", 0, "pages_read"), _DEL, 0, 2024,
     ("'pages_read'",)),
    ("pages_read not an object", "one", ("filings", 0, "pages_read"), [], 0, 2024,
     ("'pages_read'",)),
    ("pages_read.pass2 absent", "one", ("filings", 0, "pages_read", "pass2"), _DEL, 0,
     2024, ("'pages_read.pass2'",)),
    ("pages_read.pass1 page 0", "one", ("filings", 0, "pages_read", "pass1"), [0], 0,
     2024, ("'pages_read.pass1'",)),
    ("pages_read.pass1 empty", "one", ("filings", 0, "pages_read", "pass1"), [], 0,
     2024, ("'pages_read.pass1'", "empty")),
    ("historical_years absent", "one", ("filings", 0, "pass1", "historical_years"),
     _DEL, 0, 2024, ("'pass1.historical_years'",)),
    ("historical_years empty", "one", ("filings", 0, "pass1", "historical_years"),
     [], 0, 2024, ("'pass1.historical_years'",)),
    ("a year entry not an object", "one",
     ("filings", 0, "pass1", "historical_years", 0), 7, 0, 2024,
     ("historical_years[0]",)),
    ("year not an int", "one", ("filings", 0, "pass1", "historical_years", 0, "year"),
     "2023", 0, 2024, ("historical_years[0]", "'year'")),
    ("a year given twice", "one", ("filings", 0, "pass1", "historical_years", 1, "year"),
     2023, 0, 2024, ("[2023]", "more than once")),
    ("latest_balance_sheet absent", "one",
     ("filings", 0, "pass1", "latest_balance_sheet"), _DEL, 0, 2024,
     ("'pass1.latest_balance_sheet'",)),
    ("latest_balance_sheet not an object", "one",
     ("filings", 0, "pass1", "latest_balance_sheet"), [], 0, 2024,
     ("'pass1.latest_balance_sheet'",)),
    ("balance sheet year 0", "one",
     ("filings", 0, "pass1", "latest_balance_sheet", "year"), 0, 0, 2024,
     ("balance sheet", "'year'")),
    ("balance sheet figure not a number", "one",
     ("filings", 0, "pass1", "latest_balance_sheet", "long_term_debt"), "400", 0, 2024,
     ("balance sheet 2024", "'long_term_debt'")),
]


@pytest.mark.parametrize(
    ("which", "keys", "value", "index", "fiscal_year", "parts"),
    [pytest.param(*row[1:], id=row[0]) for row in _SHAPE_STOPS],
)
def test_stop_on_a_missing_or_malformed_value(
    tmp_path: Path, which: str, keys: tuple[Any, ...], value: Any,
    index: int | None, fiscal_year: int | None, parts: tuple[str, ...],
) -> None:
    data = one_filing(tmp_path) if which == "one" else three_filings(tmp_path)
    *parents, last = keys
    target: Any = data
    for key in parents:
        target = target[key]
    if value is _DEL:
        del target[last]
    else:
        target[last] = value
    path = write(tmp_path, data)
    expected = [str(path.resolve()), *parts]
    if index is not None:
        expected.append(f"filings[{index}]")
    if fiscal_year is not None:
        expected.append(pdf_name(fiscal_year))
    assert_one_line_names(stop_message(path), *expected)


def test_stop_filings_out_of_plan_order(tmp_path: Path) -> None:
    data = three_filings(tmp_path)
    data["filings"][0], data["filings"][1] = data["filings"][1], data["filings"][0]
    path = write(tmp_path, data)
    # Index 0 now holds the 2023 10-K; plan_filings puts 2022 there.
    assert_one_line_names(stop_message(path), str(path.resolve()), "filings[0]",
                          pdf_name(2023), "plan order")


def test_stop_session_file_absent(tmp_path: Path) -> None:
    path = tmp_path / "never_written.json"
    assert_one_line_names(stop_message(path), str(path.resolve()), "not found")


def test_stop_session_file_not_json(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("{ not json", encoding="utf-8")
    assert_one_line_names(stop_message(path), str(path.resolve()), "not valid JSON")


def test_stop_session_file_not_an_object(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("[]", encoding="utf-8")
    assert_one_line_names(stop_message(path), str(path.resolve()), "JSON object")


def test_main_check_and_a_bad_page_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # The command line: `check` returns the loader's exit code (0 when clean), and
    # a malformed --pages is refused with exit 2 before any PDF is opened.
    path = write(tmp_path, one_filing(tmp_path))
    assert main(["check", str(path)]) == 0
    assert main(["text", str(path), "--filing", "0", "--pages", "a-b"]) == 2
    assert "--pages" in capsys.readouterr().err
    assert main(["prompt", str(path), "--filing", "5", "--pass", "1"]) == 2
    assert "out of range" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        # _compress docstring: [1, 2, 3, 7] -> '1-3, 7'; an empty list -> 'none'.
        ([1, 2, 3, 7], "1-3, 7"),
        ([], "none"),
        ([4], "4"),
        ([1, 3, 4], "1, 3-4"),
    ],
)
def test_compress_page_numbers(numbers: list[int], expected: str) -> None:
    assert _compress(numbers) == expected
