"""Phase 2: LLM-powered universal financial data extraction layer.

Supports two providers:
  - "claude"  — Anthropic Claude (claude-sonnet-4-6 / claude-opus-4-6)
  - "gemini"  — Google Gemini   (gemini-2.5-flash / gemini-2.5-pro)

ARCHITECTURE
============
Phase 1 defines the math contract (what numbers are needed):
  ProjectionAssumptions -> capm/wacc/fcff/projector/dcf -> DCFResult

Phase 2 fills that contract from a raw 10-K/10-Q PDF:
  10-K / 10-Q PDF -> LLM (Claude or Gemini) -> FinancialStatements (Phase 1 contract)
                                              -> NonRecurringItems   (GAAP adjustments)

USAGE
=====
    from ingestion.claude_extractor import extract_financials

    financials, adj = extract_financials(
        pdf_path="GOOGL_10K_2024.pdf",
        ticker="GOOGL",
        provider="gemini",   # or "claude"
    )

ENVIRONMENT VARIABLES
=====================
    ANTHROPIC_API_KEY   — required when provider="claude"
    GEMINI_API_KEY      — required when provider="gemini"
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Literal

import pdfplumber

from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

Provider = Literal["claude", "gemini"]

# Default model IDs per provider
_DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
}


# ---------------------------------------------------------------------------
# JSON schema the LLM is asked to fill
# ---------------------------------------------------------------------------

_SCHEMA = {
    "ticker": "string",
    "company_name": "string",
    "currency": "string (e.g. 'USD')",
    "units": "string (e.g. 'Millions')",
    "historical_years": [
        {
            "year": "int — fiscal year (e.g. 2024)",
            "revenue": "float — total net revenue / net sales",
            "cost_of_revenue": "float — COGS / cost of goods sold / cost of services",
            "gross_profit": "float — revenue minus cost_of_revenue (for validation)",
            "sga": "float — SG&A combined (selling + general + admin). Positive.",
            "rd_expense": "float — R&D / research and development. Positive.",
            "depreciation_amortization": "float — depreciation and amortization can be found in the cash flow statement",
            "other_operating_expense": "float — all other operating cost lines not listed above",
            "operating_income": "float — EBIT / operating income / operating profit",
            "interest_expense": "float — interest expense on debt. POSITIVE. .",
            "interest_income": "float — interest / investment income. POSITIVE.",
            "other_non_operating": "float — net other income/expense below op line (signed)",
            "tax_expense": "float — income tax provision. POSITIVE.",
            "net_income": "float — net income attributable to common shareholders",
            "diluted_shares": "float — diluted weighted-avg shares (same units as F/S, typically millions)",
            "cfo": "float — net cash from operating activities",
            "capex": "float — capital expenditures / purchases of PP&E/ purchases of intangible assets/ acquisition. this can be found in the investing activities in the cash flow statement, do not include any securities purchases. POSITIVE.",
            "sbc": "float — stock-based compensation (add-back in operating section)",
            "cash": "float — cash and cash equivalents (balance sheet, period-end)",
            "short_term_investments": "float — marketable securities / short-term investments",
            "accounts_receivable": "float",
            "inventory": "float — 0 if not applicable",
            "other_current_assets": "float",
            "ppe_net": "float — PP&E net of accumulated depreciation",
            "goodwill": "float",
            "intangible_assets": "float — intangibles other than goodwill",
            "other_non_current_assets": "float",
            "accounts_payable": "float",
            "accrued_liabilities": "float — accrued expenses / compensation",
            "other_current_liabilities": "float",
            "short_term_debt": "float — current portion of LT debt + notes payable",
            "long_term_debt": "float — long-term debt / notes due beyond 1 year",
            "other_non_current_liabilities": "float",
            "total_equity": "float — total stockholders / shareholders equity"
        }
    ],
    "non_recurring_items": [
        {
            "year": "int",
            "description": "string — precise description",
            "amount": "float — absolute value",
            "line_item": "string — IncomeStatement field name where this item is embedded. Must be one of: cost_of_revenue | sga | rd_expense | depreciation_amortization | other_operating_expense | other_non_operating",
            "direction": "string — 'add_back' or 'remove'",
            "category": "string — restructuring|impairment|litigation|gain_loss_asset_sale|acquisition_costs|covid|other",
            "confidence": "string — high|medium|low",
            "source": "string — filing reference, e.g. 'Note 8 — Restructuring'"
        }
    ]
}

_SCHEMA_STR = json.dumps(_SCHEMA, indent=2)

# ---------------------------------------------------------------------------
# Shared system prompt (used by both providers)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent(f"""
    You are a senior financial analyst extracting structured data from SEC filings.

    You will receive the full text of a 10-K or 10-Q filing. Locate the Income
    Statement, Balance Sheet, and Cash Flow Statement, then extract the data for
    ALL fiscal years present and return a single valid JSON object matching the
    schema below.

    OUTPUT: Return ONLY the JSON object. No markdown fences, no explanation,
    no text before or after. The first character of your response must be {{.

    SCHEMA:
    {_SCHEMA_STR}

    EXTRACTION RULES:
    - Extract ALL fiscal years present in the filing (typically 3-5 years).
    - All monetary values: use the same currency and units as the source (usually USD Millions).
    - All values must be POSITIVE numbers (expenses, costs, taxes, capex).
      Signs are implied by the field name, not the value.
    - If a line item is not reported or not applicable, use 0.
    - Do NOT invent or estimate numbers. Only use what is explicitly stated.
    - Balance sheet values are period-END (not averages).
    - For "sga": combine Sales & Marketing + General & Administrative if reported separately.
      line on the income statement. Do NOT pull this from the cash flow statement.
    - For "interest_expense": gross interest on debt (positive). don't put the net interest expense here, go to the footnote and find the berakout of the gross interest expense.
    - For "cfo": use the total "Net cash provided by operating activities" line.
    - For "capex": acquisition or purchases of PP&E/ purchases of intangible assets.(absolute value).
      Do not include securities purchases.

    NON-RECURRING ITEM RULES:
    - Read MD&A and Notes to Financial Statements for one-time, non-recurring,
      unusual, or infrequent items such as:
        * Restructuring / severance charges
        * Goodwill / asset impairment write-downs
        * Gains or losses on sale of assets / business units
        * Legal settlements / litigation charges
        * Acquisition / integration costs
    - For line_item: use the exact IncomeStatement field name where the item is
      embedded (cost_of_revenue | sga | rd_expense | depreciation_amortization |
      other_operating_expense | other_non_operating).
    - direction: "add_back" for one-time expenses; "remove" for one-time gains.
    - Only flag items with clear evidence in the filing.
    - Return non_recurring_items: [] if none found.
""").strip()


# ---------------------------------------------------------------------------
# Arithmetic validation
# ---------------------------------------------------------------------------

def _validate_extracted_data(
    llm_years: list[dict],
    warn_pct: float = 0.5,
    fail_pct: float = 2.0,
) -> None:
    """Arithmetic reconciliation of LLM-extracted P&L data.

    Verifies that the LLM's stated subtotals (gross_profit, operating_income,
    net_income) can be re-derived from the component line items it returned.
    Raises ValueError if any mismatch exceeds fail_pct.
    """
    print(f"\n{'='*65}")
    print("EXTRACTED DATA VALIDATION — ARITHMETIC CHECK")
    print(f"{'='*65}")
    print(f"  {'Year':<6}  {'Field':<18}  {'Stated':>10}  {'Derived':>10}  {'Diff':>9}  Status")
    print(f"  {'-'*64}")

    failures: list[str] = []

    for yr in sorted(llm_years, key=lambda x: x["year"]):
        year       = int(yr["year"])
        rev        = float(yr.get("revenue",                   0))
        cogs       = float(yr.get("cost_of_revenue",           0))
        gp_stated  = float(yr.get("gross_profit",              0))
        sga        = float(yr.get("sga",                       0))
        rd         = float(yr.get("rd_expense",                0))
        other_opex = float(yr.get("other_operating_expense",   0))
        ebit_stated= float(yr.get("operating_income",         0))
        int_exp    = float(yr.get("interest_expense",          0))
        int_inc    = float(yr.get("interest_income",           0))
        other_nop  = float(yr.get("other_non_operating",       0))
        tax        = float(yr.get("tax_expense",               0))
        ni_stated  = float(yr.get("net_income",                0))

        # DA is broken out of other_opex in the IS model (net zero on EBIT),
        # so the raw-JSON check excludes DA to avoid double-counting.
        gp_derived   = rev - cogs
        ebit_derived = gp_derived - sga - rd - other_opex
        ni_derived   = ebit_derived + int_inc - int_exp + other_nop - tax

        for label, stated, derived in [
            ("Gross Profit", gp_stated,   gp_derived),
            ("Oper. Income", ebit_stated, ebit_derived),
            ("Net Income",   ni_stated,   ni_derived),
        ]:
            if stated == 0 and derived == 0:
                continue
            diff     = stated - derived
            base     = abs(stated) if stated else abs(derived)
            diff_pct = abs(diff) / base * 100 if base else 0.0
            if diff_pct > fail_pct:
                status = "FAIL"
                failures.append(
                    f"  [{year}] {label}: stated={stated:,.0f}  "
                    f"derived={derived:,.0f}  diff={diff:+,.0f}"
                )
            elif diff_pct > warn_pct:
                status = "WARN"
            else:
                status = "OK"
            print(f"  {year:<6}  {label:<18}  {stated:>10,.0f}  {derived:>10,.0f}  {diff:>+9,.0f}  {status}")

    print(f"\n{'='*65}")

    if failures:
        raise ValueError("LLM extraction validation FAILED:\n" + "\n".join(failures))


# ---------------------------------------------------------------------------
# PDF reader — full document, no section pre-filtering
# ---------------------------------------------------------------------------

def _read_pdf_text(path: str | Path, max_pages: int = 300) -> str:
    """Extract text from all pages of a 10-K/10-Q PDF up to max_pages.

    The LLM receives the complete document so it can locate financial statements
    and MD&A itself without Python-side section detection.
    """
    with pdfplumber.open(str(path)) as pdf:
        n = len(pdf.pages)
        limit = min(max_pages, n)
        pages: list[str] = []
        for i in range(limit):
            text = (pdf.pages[i].extract_text() or "").strip()
            if text:
                pages.append(f"--- Page {i + 1} ---\n{text}")
        print(f"  PDF: {limit} of {n} pages extracted")
    return "\n\n".join(pages)


def _build_user_prompt(pdf_text: str) -> str:
    return (
        "Extract the financial data from the following 10-K/10-Q filing.\n\n"
        "=== 10-K / 10-Q FILING (PDF text) ===\n"
        + pdf_text
    )


# ---------------------------------------------------------------------------
# JSON cleaner
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Strip markdown fences and return the outermost JSON object."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM response.\nRaw (first 500 chars):\n{raw[:500]}")
    return raw[start: end + 1]


# ---------------------------------------------------------------------------
# Provider-specific API calls
# ---------------------------------------------------------------------------

def _call_claude(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_key: str,
) -> tuple[str, int, int]:
    """Call Anthropic Claude. Returns (response_text, input_tokens, output_tokens)."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = response.content[0].text
    return text, response.usage.input_tokens, response.usage.output_tokens


def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_key: str,
) -> tuple[str, int, int]:
    """Call Google Gemini. Returns (response_text, input_tokens, output_tokens)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=32768,
            temperature=0.0,                    # deterministic extraction
            response_mime_type="application/json",  # force valid JSON output
        ),
    )
    # Log finish reason so truncation issues are visible
    finish_reason = None
    if response.candidates:
        finish_reason = str(response.candidates[0].finish_reason)
    text = response.text or ""
    # Token counts (may be None for some models/responses)
    in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    if finish_reason and finish_reason not in ("FinishReason.STOP", "STOP", "1"):
        print(f"  [WARN] Gemini finish_reason={finish_reason} — response may be truncated")
    return text, in_tok, out_tok


# ---------------------------------------------------------------------------
# Response parser — LLM JSON -> domain objects
# ---------------------------------------------------------------------------

def _parse_llm_response(
    json_str: str,
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Convert LLM JSON output into Phase 1 domain objects."""
    data = json.loads(json_str)
    _validate_extracted_data(data.get("historical_years", []))

    income_statements: list[IncomeStatement] = []
    balance_sheets: list[BalanceSheet] = []
    cash_flow_statements: list[CashFlowStatement] = []

    for yr in data.get("historical_years", []):
        year = int(yr["year"])

        income_statements.append(IncomeStatement(
            year=year,
            revenue=float(yr.get("revenue", 0)),
            cost_of_revenue=float(yr.get("cost_of_revenue", 0)),
            sga=float(yr.get("sga", 0)),
            rd_expense=float(yr.get("rd_expense", 0)),
            depreciation_amortization=float(yr.get("depreciation_amortization", 0)),
            other_operating_expense=float(yr.get("other_operating_expense", 0)) - float(yr.get("depreciation_amortization", 0)),
            interest_expense=float(yr.get("interest_expense", 0)),
            interest_income=float(yr.get("interest_income", 0)),
            other_non_operating=float(yr.get("other_non_operating", 0)),
            tax_expense=float(yr.get("tax_expense", 0)),
            diluted_shares_outstanding=float(yr.get("diluted_shares", 0)),
        ))

        balance_sheets.append(BalanceSheet(
            year=year,
            cash_and_equivalents=float(yr.get("cash", 0)),
            short_term_investments=float(yr.get("short_term_investments", 0)),
            accounts_receivable=float(yr.get("accounts_receivable", 0)),
            inventory=float(yr.get("inventory", 0)),
            other_current_assets=float(yr.get("other_current_assets", 0)),
            ppe_net=float(yr.get("ppe_net", 0)),
            goodwill=float(yr.get("goodwill", 0)),
            intangible_assets=float(yr.get("intangible_assets", 0)),
            other_non_current_assets=float(yr.get("other_non_current_assets", 0)),
            accounts_payable=float(yr.get("accounts_payable", 0)),
            short_term_debt=float(yr.get("short_term_debt", 0)),
            current_portion_lt_debt=0.0,
            accrued_liabilities=float(yr.get("accrued_liabilities", 0)),
            other_current_liabilities=float(yr.get("other_current_liabilities", 0)),
            long_term_debt=float(yr.get("long_term_debt", 0)),
            other_non_current_liabilities=float(yr.get("other_non_current_liabilities", 0)),
            total_equity=float(yr.get("total_equity", 0)),
        ))

        # Reconstruct CFS so cash_from_operations == cfo exactly
        cfo = float(yr.get("cfo", 0))
        net_income = float(yr.get("net_income", 0))
        da = float(yr.get("depreciation_amortization", 0))
        sbc = float(yr.get("sbc", 0))
        capex = float(yr.get("capex", 0))
        other_ops = cfo - net_income - da - sbc   # residual

        cash_flow_statements.append(CashFlowStatement(
            year=year,
            net_income=net_income,
            depreciation_amortization=da,
            stock_based_compensation=sbc,
            change_in_working_capital=0.0,
            other_operating_activities=other_ops,
            capital_expenditures=-capex,   # stored as negative per convention
            acquisitions=0.0,
            other_investing_activities=0.0,
            debt_issued=0.0,
            debt_repaid=0.0,
            shares_issued=0.0,
            shares_repurchased=0.0,
            dividends_paid=0.0,
            other_financing_activities=0.0,
        ))

    non_recurring = [
        NonRecurringItem(
            year=int(item["year"]),
            description=item["description"],
            amount=float(item["amount"]),
            line_item=item["line_item"],
            direction=item["direction"],
            category=item["category"],
            confidence=item.get("confidence", "high"),
            source=item.get("source", ""),
        )
        for item in data.get("non_recurring_items", [])
    ]

    financials = FinancialStatements(
        ticker=ticker or data.get("ticker", ""),
        company_name=company_name or data.get("company_name", ""),
        income_statements=sorted(income_statements, key=lambda x: x.year),
        balance_sheets=sorted(balance_sheets, key=lambda x: x.year),
        cash_flow_statements=sorted(cash_flow_statements, key=lambda x: x.year),
    )
    return financials, non_recurring


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_financials(
    pdf_path: str | Path,
    ticker: str = "",
    company_name: str = "",
    provider: Provider = "claude",
    model: str | None = None,
    max_pdf_pages: int = 300,
    debug: bool = False,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Extract structured financial data from a 10-K/10-Q PDF using an LLM.

    Args:
        pdf_path:     Path to the 10-K or 10-Q PDF filing.
        ticker:       Stock ticker (used to label output).
        company_name: Company name (used to label output).
        provider:     "claude" (Anthropic) or "gemini" (Google).
        model:        Override the default model for the chosen provider.
                      Defaults: claude-sonnet-4-6 / gemini-2.5-flash
                      Alternatives:
                        Claude  — "claude-opus-4-6"  (most capable)
                        Gemini  — "gemini-2.5-pro"   (most capable)
                                  "gemini-1.5-pro"   (1M context for very long PDFs)
        max_pdf_pages: Maximum pages to extract from the PDF (default 300).
        debug:        Print raw LLM response when True.

    Environment variables required:
        ANTHROPIC_API_KEY  — when provider="claude"
        GEMINI_API_KEY     — when provider="gemini"

    Returns:
        (FinancialStatements, list[NonRecurringItem])
    """
    if provider not in ("claude", "gemini"):
        raise ValueError(f"provider must be 'claude' or 'gemini', got '{provider}'")

    resolved_model = model or _DEFAULT_MODELS[provider]

    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

    # --- Read PDF ---
    print(f"  Provider: {provider.upper()}  |  Model: {resolved_model}")
    print(f"  Reading PDF: {Path(pdf_path).name}")
    pdf_text = _read_pdf_text(pdf_path, max_pages=max_pdf_pages)
    user_prompt = _build_user_prompt(pdf_text)

    # --- Call LLM ---
    print(f"  Calling {provider.upper()} API...")
    if provider == "claude":
        raw, in_tok, out_tok = _call_claude(SYSTEM_PROMPT, user_prompt, resolved_model, api_key)
    else:
        raw, in_tok, out_tok = _call_gemini(SYSTEM_PROMPT, user_prompt, resolved_model, api_key)

    if in_tok or out_tok:
        print(f"  Tokens used — input: {in_tok:,}  output: {out_tok:,}")

    if debug:
        print("\n" + "=" * 65)
        print("RAW LLM RESPONSE")
        print("=" * 65)
        print(raw)
        print("=" * 65 + "\n")

    # --- Parse + Validate ---
    json_str = _extract_json(raw)
    try:
        return _parse_llm_response(json_str, ticker, company_name)
    except json.JSONDecodeError as exc:
        ctx_start = max(0, exc.pos - 120)
        ctx_end = min(len(json_str), exc.pos + 120)
        print(f"\n  [JSON parse error] {exc}")
        print(f"  Context around position {exc.pos}:\n  ...{json_str[ctx_start:ctx_end]}...")

        print(f"\n  Retrying — asking {provider.upper()} to repair the JSON...")
        fix_prompt = (
            "The following JSON is malformed. Return ONLY the corrected JSON object "
            "with no markdown fences and no additional text.\n\n"
            + json_str
        )
        if provider == "claude":
            raw2, _, _ = _call_claude(SYSTEM_PROMPT, fix_prompt, resolved_model, api_key)
        else:
            raw2, _, _ = _call_gemini(SYSTEM_PROMPT, fix_prompt, resolved_model, api_key)
        json_str2 = _extract_json(raw2)
        return _parse_llm_response(json_str2, ticker, company_name)
