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
    "gemini": "gemini-3-flash-preview",
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
            "interest_expense": "float — interest expense on debt. POSITIVE.",
            "interest_income": "float — interest / investment income. POSITIVE.",
            "other_non_operating": "float — net other income/expense below op line (signed)",
            "tax_expense": "float — income tax provision. POSITIVE.",
            "net_income": "float — net income attributable to common shareholders",
            "diluted_shares": "float — diluted weighted-avg shares (same units as F/S, typically millions)",
            "cfo": "float — net cash from operating activities",
            "capex": "float — SUM of ALL non-securities investing outflows from the cash flow statement investing section: 'Purchases of property and equipment' PLUS 'Acquisitions, net of cash acquired, and purchases of intangible assets'. Add both lines together. Do NOT include purchases/sales of marketable or non-marketable securities. POSITIVE.",
            "sbc": "float — stock-based compensation (add-back in operating section)",
            "change_in_working_capital": "float — total 'Changes in assets and liabilities, net of acquisitions' from operating activities in the cash flow statement. SIGNED: negative when net working capital increases (cash outflow), positive when it decreases (cash inflow). This is the SUM of all individual asset/liability change lines (e.g. change in accounts receivable, change in accounts payable, etc.).",
        }
    ],
    "latest_balance_sheet": {
        "year": "int — the most recent fiscal year in the filing",
        "cash": "float — cash and cash equivalents (period-end)",
        "short_term_investments": "float — marketable securities / short-term investments",
        "accounts_receivable": "float",
        "inventory": "float — 0 if not applicable",
        "other_current_assets": "float — ALL other current assets not listed above (prepaid, deferred, etc.)",
        "ppe_net": "float — PP&E net of accumulated depreciation",
        "goodwill": "float",
        "intangible_assets": "float — intangibles other than goodwill",
        "other_non_current_assets": "float — CATCH-ALL: SUM of every non-current asset NOT already listed above. Includes non-marketable securities, deferred income taxes (asset), operating lease right-of-use assets, equity method investments, and any other line items. This field must make total_non_current_assets balance.",
        "accounts_payable": "float",
        "accrued_liabilities": "float — accrued expenses / accrued compensation and benefits",
        "other_current_liabilities": "float — CATCH-ALL: SUM of every current liability NOT already listed above. Includes accrued revenue share, deferred revenue, accrued expenses and other current liabilities, and any other line items.",
        "short_term_debt": "float — current portion of LT debt + notes payable + commercial paper",
        "long_term_debt": "float — long-term debt / notes due beyond 1 year",
        "other_non_current_liabilities": "float — CATCH-ALL: SUM of every non-current liability NOT already listed above. Includes non-current income taxes payable, operating lease liabilities, pension obligations, deferred tax liabilities, and any other line items.",
        "total_equity": "float — total stockholders / shareholders equity",
    },
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
    Statement, Balance Sheet, and Cash Flow Statement, then extract the data and
    return a single valid JSON object matching the schema below.

    OUTPUT: Return ONLY the JSON object. No markdown fences, no explanation,
    no text before or after. The first character of your response must be {{.

    SCHEMA:
    {_SCHEMA_STR}

    EXTRACTION RULES:
    - "historical_years": extract Income Statement and Cash Flow data for ALL
      fiscal years present in the filing (typically 2-3 years).
    - "latest_balance_sheet": extract Balance Sheet data for ONLY the most
      recent fiscal year end in the filing.
    - All monetary values: use the same currency and units as the source (usually USD Millions).
    - All values must be POSITIVE numbers (expenses, costs, taxes, capex).
      Signs are implied by the field name, not the value.
    - If a line item is not reported or not applicable, use 0.
    - Do NOT invent or estimate numbers. Only use what is explicitly stated.
    - For "sga": combine Sales & Marketing + General & Administrative if reported separately.
      line on the income statement. Do NOT pull this from the cash flow statement.
    - For "interest_expense": gross interest on debt (positive). don't put the net interest expense here, go to the footnote and find the berakout of the gross interest expense.
    - For "cfo": use the total "Net cash provided by operating activities" line.
    - For "capex": SUM of 'Purchases of property and equipment' PLUS 'Acquisitions, net of
      cash acquired, and purchases of intangible assets' from the investing section of the
      cash flow statement. You MUST add BOTH lines together. Do NOT include purchases/sales
      of marketable or non-marketable securities. Return the absolute value (positive).

    BALANCE SHEET RULES (latest_balance_sheet only):
    - CRITICAL: The balance sheet MUST balance: Total Assets = Total Liabilities + Total Equity.
    - The "other_" catch-all fields (other_current_assets, other_non_current_assets,
      other_current_liabilities, other_non_current_liabilities) must capture ALL line items
      not mapped to a named field. Sum every remaining line into the appropriate catch-all.
    - After filling all fields, verify: sum of asset fields = total_equity + sum of liability fields.
      If they don't balance, adjust the catch-all fields to close the gap.

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
    fail_pct: float = 1.0,
) -> list[str]:
    """Arithmetic reconciliation of LLM-extracted I/S data.

    Verifies that the LLM's stated subtotals (gross_profit, operating_income,
    net_income) can be re-derived from the component line items it returned.

    Returns a list of error descriptions (empty = all passed).
    """
    print(f"\n{'='*65}")
    print("EXTRACTED DATA VALIDATION — ARITHMETIC CHECK")
    print(f"{'='*65}")
    print(f"  {'Year':<6}  {'Field':<18}  {'Stated':>10}  {'Derived':>10}  {'Diff':>9}  Status")
    print(f"  {'-'*64}")

    errors: list[str] = []

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

        for label, stated, derived, formula in [
            ("Gross Profit", gp_stated, gp_derived,
             f"revenue({rev:,.0f}) - cost_of_revenue({cogs:,.0f})"),
            ("Oper. Income", ebit_stated, ebit_derived,
             f"gross_profit({gp_derived:,.0f}) - sga({sga:,.0f}) - rd_expense({rd:,.0f}) - other_operating_expense({other_opex:,.0f})"),
            ("Net Income", ni_stated, ni_derived,
             f"operating_income({ebit_derived:,.0f}) + interest_income({int_inc:,.0f}) - interest_expense({int_exp:,.0f}) + other_non_operating({other_nop:,.0f}) - tax_expense({tax:,.0f})"),
        ]:
            if stated == 0 and derived == 0:
                continue
            diff     = stated - derived
            base     = abs(stated) if stated else abs(derived)
            diff_pct = abs(diff) / base * 100 if base else 0.0
            if diff_pct > fail_pct:
                status = "FAIL"
                errors.append(
                    f"[{year}] {label}: stated={stated:,.0f} but derived={derived:,.0f} "
                    f"(diff={diff:+,.0f}). Derivation: {formula} = {derived:,.0f}. "
                    f"Fix the component fields so they reconcile to your stated {label}."
                )
            elif diff_pct > 0.5:
                status = "WARN"
            else:
                status = "OK"
            print(f"  {year:<6}  {label:<18}  {stated:>10,.0f}  {derived:>10,.0f}  {diff:>+9,.0f}  {status}")

    print(f"\n{'='*65}")

    return errors


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
            max_output_tokens=65536,            # enough for thinking + JSON response
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
) -> tuple[FinancialStatements, list[NonRecurringItem], list[str]]:
    """Convert LLM JSON output into Phase 1 domain objects.

    Returns (FinancialStatements, NonRecurringItems, validation_errors).
    """
    data = json.loads(json_str)
    validation_errors = _validate_extracted_data(data.get("historical_years", []))

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

        # Reconstruct CFS so cash_from_operations == cfo exactly
        cfo = float(yr.get("cfo", 0))
        net_income = float(yr.get("net_income", 0))
        da = float(yr.get("depreciation_amortization", 0))
        sbc = float(yr.get("sbc", 0))
        capex = float(yr.get("capex", 0))
        delta_wc = float(yr.get("change_in_working_capital", 0))  # CFS convention: negative = outflow
        other_ops = cfo - net_income - da - sbc - delta_wc   # residual

        cash_flow_statements.append(CashFlowStatement(
            year=year,
            net_income=net_income,
            depreciation_amortization=da,
            stock_based_compensation=sbc,
            change_in_working_capital=delta_wc,
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

    # Parse latest_balance_sheet (single object, not per-year)
    bs_data = data.get("latest_balance_sheet", {})
    if bs_data:
        balance_sheets.append(BalanceSheet(
            year=int(bs_data.get("year", 0)),
            cash_and_equivalents=float(bs_data.get("cash", 0)),
            short_term_investments=float(bs_data.get("short_term_investments", 0)),
            accounts_receivable=float(bs_data.get("accounts_receivable", 0)),
            inventory=float(bs_data.get("inventory", 0)),
            other_current_assets=float(bs_data.get("other_current_assets", 0)),
            ppe_net=float(bs_data.get("ppe_net", 0)),
            goodwill=float(bs_data.get("goodwill", 0)),
            intangible_assets=float(bs_data.get("intangible_assets", 0)),
            other_non_current_assets=float(bs_data.get("other_non_current_assets", 0)),
            accounts_payable=float(bs_data.get("accounts_payable", 0)),
            short_term_debt=float(bs_data.get("short_term_debt", 0)),
            current_portion_lt_debt=0.0,
            accrued_liabilities=float(bs_data.get("accrued_liabilities", 0)),
            other_current_liabilities=float(bs_data.get("other_current_liabilities", 0)),
            long_term_debt=float(bs_data.get("long_term_debt", 0)),
            other_non_current_liabilities=float(bs_data.get("other_non_current_liabilities", 0)),
            total_equity=float(bs_data.get("total_equity", 0)),
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
    return financials, non_recurring, validation_errors


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

    import os
    # dotenv is loaded by config.py at import time; keys come from
    # .env file OR system environment — no intermediate config vars needed.
    import config as _  # noqa: F401 — triggers dotenv load

    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set. Add it to .env or system env.")
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Add it to .env or system env.")

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

    # --- Parse + Validate + Feedback loop ---
    MAX_RETRIES = 2
    json_str = _extract_json(raw)

    for attempt in range(1 + MAX_RETRIES):
        # Handle malformed JSON
        try:
            financials, non_recurring, val_errors = _parse_llm_response(json_str, ticker, company_name)
        except json.JSONDecodeError as exc:
            ctx_start = max(0, exc.pos - 120)
            ctx_end = min(len(json_str), exc.pos + 120)
            print(f"\n  [JSON parse error] {exc}")
            print(f"  Context around position {exc.pos}:\n  ...{json_str[ctx_start:ctx_end]}...")

            if attempt >= MAX_RETRIES:
                raise
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
            json_str = _extract_json(raw2)
            continue

        # Validation passed — return
        if not val_errors:
            return financials, non_recurring

        # Validation failed — feedback loop
        if attempt >= MAX_RETRIES:
            print(f"\n  [WARN] Validation errors remain after {MAX_RETRIES} retries:")
            for e in val_errors:
                print(f"    {e}")
            return financials, non_recurring

        print(f"\n  Validation errors found — sending feedback to {provider.upper()} (retry {attempt + 1}/{MAX_RETRIES})...")
        error_list = "\n".join(f"  - {e}" for e in val_errors)
        fix_prompt = (
            "The following JSON was extracted from a 10-K filing but has arithmetic "
            "errors in the income statement. The stated subtotals do not match the "
            "component line items.\n\n"
            "ERRORS:\n" + error_list + "\n\n"
            "Fix the JSON so that ALL of these reconcile exactly:\n"
            "  gross_profit = revenue - cost_of_revenue\n"
            "  operating_income = gross_profit - sga - rd_expense - other_operating_expense\n"
            "  net_income = operating_income + interest_income - interest_expense + other_non_operating - tax_expense\n\n"
            "If a subtotal is correct, adjust the component fields. If the components "
            "are correct, adjust the subtotal. Use ONLY numbers from the original filing.\n\n"
            "Return ONLY the corrected JSON object. No markdown fences, no explanation.\n\n"
            + json_str
        )
        if provider == "claude":
            raw2, in2, out2 = _call_claude(SYSTEM_PROMPT, fix_prompt, resolved_model, api_key)
        else:
            raw2, in2, out2 = _call_gemini(SYSTEM_PROMPT, fix_prompt, resolved_model, api_key)
        if in2 or out2:
            print(f"  Retry tokens — input: {in2:,}  output: {out2:,}")
        json_str = _extract_json(raw2)

    return financials, non_recurring
