"""Two-pass LLM extraction for 10-K/10-Q SEC filings.

ARCHITECTURE
============
  PASS 1 — Financial Statements (year-targeted, table extraction)
    PDF → LLM → I/S + C/F (+ optional B/S) for target years only
    Prompt focused on number precision and arithmetic reconciliation.

  PASS 2 — Non-Recurring Items (year-targeted, footnote reasoning)
    PDF + I/S summary from Pass 1 → LLM → NonRecurringItem list
    Prompt focused on semantic reading of MD&A and notes.

Why two passes?
  - Table extraction (precision) and footnote reasoning (semantics) are
    fundamentally different tasks. A single prompt forces the LLM to do both,
    and neither gets full attention.
  - Pass 2 receives the extracted I/S as context, so it can anchor NRI amounts
    to concrete line items and verify plausibility.

SMART MULTI-PDF ORCHESTRATOR
=============================
When multiple 10-K PDFs are provided (e.g. 2025, 2024, 2023 filings):
  - Oldest filing: extract ALL years (picks up comparative years)
  - Other filings: extract ONLY the primary fiscal year
  - Balance sheet: only from the most recent filing

Example with 3 filings:
  2025 10-K → extract [2025] + B/S          (1 year,  2 API calls)
  2024 10-K → extract [2024] only           (1 year,  2 API calls)
  2023 10-K → extract [2023, 2022, 2021]    (3 years, 2 API calls)
  Total: 5 unique years, 6 API calls
  Old way: 9 year-extractions, 3 API calls — but each call was overloaded

USAGE
=====
    from ingestion.claude_extractor import extract_financials, extract_multi_year

    # Single PDF (both passes, extracts all years)
    financials, nri = extract_financials("GOOGL_10K_2025.pdf", ticker="GOOGL")

    # Multi-year smart extraction
    financials, nri = extract_multi_year(
        filings=[
            (2025, "GOOGL_10K_2025.pdf"),
            (2024, "GOOGL_10K_2024.pdf"),
            (2023, "GOOGL_10K_2023.pdf"),
        ],
        ticker="GOOGL",
    )

PROVIDER, TRANSPORT AND CREDENTIAL
==================================
There are two *providers* — Claude and Gemini — and the default is named once, in
`config.DEFAULT_EXTRACTION_PROVIDER`. Nothing in this file, in `api/` or in `cli.py`
carries a second provider default.

A **transport** is not a provider. Claude can be reached two ways, and the model is
the same Claude either way:

    ANTHROPIC_FOUNDRY_BASE_URL / _RESOURCE set  → anthropic.AnthropicFoundry
                                                  (a Microsoft Foundry gateway)
    otherwise                                   → anthropic.Anthropic
                                                  (the public Anthropic API)

Which model read the filing, over which transport, on whose credential, is an
assumption about every figure downstream — rule 6. `resolve_provider` returns that
as a `ProviderResolution`, the CLI prints it and the web result page shows it.

ENVIRONMENT VARIABLES
=====================
    ANTHROPIC_FOUNDRY_BASE_URL  — the Foundry gateway endpoint. Setting it (or
                                  ANTHROPIC_FOUNDRY_RESOURCE) selects the Foundry
                                  transport for provider="claude".
    ANTHROPIC_FOUNDRY_API_KEY   — optional. When absent, the Foundry transport uses
                                  an Entra ID token from DefaultAzureCredential,
                                  which on a developer machine means `az login`.
    ANTHROPIC_API_KEY           — required for provider="claude" when no Foundry
                                  gateway is configured.
    GEMINI_API_KEY              — required when provider="gemini".

See docs/8-build/environment.md section 3.
"""

from __future__ import annotations

import base64
import json
import os
import re
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

import config

if TYPE_CHECKING:  # the SDKs are imported lazily at the call site, not at import time
    import anthropic

from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

Provider = Literal["claude", "gemini"]

# How the request reaches the provider. NOT a third provider — the model served over
# "foundry" is the same Claude served over "anthropic-direct".
#
# "claude-code-session" is the same reasoning carried one step further: the figures
# were read by Claude inside a Claude Code session and stored in a session file
# (ingestion/session_extraction.py). The model is still Claude, so the provider is
# still "claude"; only the road the PDF took to the model changed, and on this road
# no API request is made at all. docs/8-build/environment.md section 3.
Transport = Literal[
    "foundry", "anthropic-direct", "gemini-direct", "claude-code-session",
]

# Which credential the transport carries. The kind, never the value.
# "claude-code-session" carries none: the session file is read from disk.
CredentialKind = Literal[
    "foundry-api-key", "entra-token", "anthropic-api-key", "gemini-api-key",
    "claude-code-session",
]


@dataclass(frozen=True)
class ProviderResolution:
    """Who read the filing, over what, on whose credential.

    Every field is a label. **No field holds a key or a token**, so this object is
    safe to print and to render into a page — which is the point of it: rule 6 says
    an assumption is shown to the reader, and "claude-opus-5 via a company gateway"
    and "claude-opus-5 via the public API" must be distinguishable in the output.
    """

    provider: Provider
    model: str
    transport: Transport
    transport_label: str
    credential: CredentialKind
    credential_source: str


# Default model IDs per provider. A lookup of a *string*, not of behaviour.
# claude-opus-5 is the model decided on 2026-09-20 and is served by the Foundry
# gateway on this network (measured, docs/8-build/environment.md section 3).
# gemini-3-flash-preview is the other Gemini model available.
_DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-opus-5",
    "gemini": "gemini-3.1-pro-preview",
}


# ===========================================================================
# PASS 1: Financial Statement Extraction — schema & prompt
# ===========================================================================

# One historical year of Pass 1. Named on its own so the session route can require
# every key it names (PASS1_YEAR_FIELDS, below) without importing a private name,
# and so the two cannot drift: the prompt's schema text is built from this dict.
_FINANCIALS_YEAR_SCHEMA: dict[str, str] = {
    "year": "int — fiscal year (e.g. 2024)",
    "revenue": "float — total net revenue / net sales",
    "cost_of_revenue": "float — COGS / cost of goods sold / cost of services",
    "gross_profit": "float — revenue minus cost_of_revenue (for validation)",
    "sga": "float — SG&A combined (selling + general + admin). Positive.",
    "rd_expense": "float — R&D / research and development. Positive.",
    "depreciation_amortization": "float — D&A from cash flow statement operating section",
    "other_operating_expense": "float — all other operating cost lines not listed above",
    "operating_income": "float — EBIT, income from operating activities, this should be from income statement",
    "interest_expense": "float — gross interest expense on debt. POSITIVE. Use footnote breakout if I/S shows only net interest.",
    "interest_income": "float — interest / investment income. POSITIVE.",
    "other_non_operating": "float — net other income/expense below operating line (signed)",
    "tax_expense": "float — income tax provision. POSITIVE.",
    "net_income": "float — TOTAL CONSOLIDATED net income (net income INCLUDING noncontrolling interests, i.e. EBT minus tax_expense, BEFORE any allocation to noncontrolling interests). Do NOT use 'net income attributable to common shareholders' or 'attributable to the parent'.",
    "diluted_shares": "float — diluted weighted-avg shares (same units as F/S)",
    "cfo": "float — net cash provided by operating activities",
    "capex": "float — SUM of 'Purchases of PP&E' PLUS 'Acquisitions and intangible asset purchases' from investing section. Do NOT include securities. POSITIVE.",
    "sbc": "float — stock-based compensation (from CFS operating section)",
    "change_in_working_capital": "float — total 'Changes in assets and liabilities' from Cash Flow Statement operating section. SIGNED: negative = WC increase (cash outflow), positive = WC decrease (cash inflow).",
}

# The one balance sheet Pass 1 returns when the plan asks for it.
_FINANCIALS_BALANCE_SHEET_SCHEMA: dict[str, str] = {
    "year": "int — the most recent fiscal year in the filing",
    "cash": "float — cash and cash equivalents (period-end)",
    "short_term_investments": "float — marketable securities / short-term investments",
    "accounts_receivable": "float",
    "inventory": "float — 0 if not applicable",
    "other_current_assets": "float — ALL other current assets not listed above",
    "ppe_net": "float — PP&E net of accumulated depreciation",
    "goodwill": "float",
    "intangible_assets": "float — intangibles other than goodwill",
    "other_non_current_assets": "float — CATCH-ALL for all non-current assets not listed above. Includes non-marketable securities, deferred income taxes (asset), operating lease ROU assets, equity method investments, etc.",
    "accounts_payable": "float",
    "accrued_liabilities": "float — accrued expenses / compensation",
    "other_current_liabilities": "float — CATCH-ALL for all current liabilities not listed above. Includes deferred revenue, accrued revenue share, etc.",
    "short_term_debt": "float — current portion of LT debt + notes payable + commercial paper",
    "long_term_debt": "float — long-term debt beyond 1 year",
    "other_non_current_liabilities": "float — CATCH-ALL for all non-current liabilities not listed above. Includes operating lease liabilities, pension, deferred tax liabilities, etc.",
    "total_equity": "float — total stockholders equity",
    "noncontrolling_interest_nonredeemable": "float — MEMO: the noncontrolling interest line printed INSIDE equity on the latest balance sheet (e.g. 'Nonredeemable noncontrolling interest'). 0 if the filing prints none. It is already inside total_equity; never add it to any total.",
    "noncontrolling_interest_redeemable": "float — MEMO: the redeemable noncontrolling interest line printed OUTSIDE equity (mezzanine, between liabilities and equity) on the latest balance sheet. 0 if the filing prints none. It is already inside another line; never add it to any total.",
}

_FINANCIALS_SCHEMA = {
    "ticker": "string",
    "company_name": "string",
    "currency": "string (e.g. 'USD')",
    "units": "string (e.g. 'Millions')",
    "historical_years": [_FINANCIALS_YEAR_SCHEMA],
    "latest_balance_sheet": _FINANCIALS_BALANCE_SHEET_SCHEMA,
}

# Every key a Pass 1 answer must carry, per historical year and in the balance sheet.
# Route A's parser does not require them (it reads an absent field as zero, backlog item 1).
# The session route's loader does, on purpose; see ingestion/session_extraction.py.
PASS1_YEAR_FIELDS: tuple[str, ...] = tuple(_FINANCIALS_YEAR_SCHEMA)
PASS1_BALANCE_SHEET_FIELDS: tuple[str, ...] = tuple(_FINANCIALS_BALANCE_SHEET_SCHEMA)

_FINANCIALS_SCHEMA_STR = json.dumps(_FINANCIALS_SCHEMA, indent=2)

_FINANCIALS_SYSTEM_PROMPT = textwrap.dedent(f"""\
    You are a senior financial analyst. Your ONLY task is to extract numerical
    financial data from a 10-K/10-Q filing — Income Statement, Cash Flow
    Statement, and (if requested) Balance Sheet.

    OUTPUT: Return ONLY a valid JSON object. No markdown fences, no explanation.
    The first character of your response must be {{.

    SCHEMA:
    {_FINANCIALS_SCHEMA_STR}

    EXTRACTION RULES:
    - Extract ONLY the fiscal years specified in the user instructions.
    - All monetary values: same currency and units as the source (usually USD Millions).
    - All values must be POSITIVE (signs implied by field name).
    - If a line item is not reported, use 0.
    - Do NOT invent or estimate numbers. Only extract what is explicitly stated.
    - For "sga": combine Sales & Marketing + General & Administrative if separate.
    - For "interest_expense": gross interest on debt (positive). Go to footnotes
      for the breakout if only net interest is on the I/S.
    - For "cfo": use the total "Net cash provided by operating activities".
    - For "net_income": use TOTAL CONSOLIDATED net income (includes noncontrolling
      interests; equals EBT minus tax). NEVER use "net income attributable to
      common shareholders / to the parent", which is net of noncontrolling interests.
    - For "capex": SUM of 'Purchases of PP&E' PLUS 'Acquisitions/intangible asset
      purchases' from investing section. Do NOT include securities. Absolute value.
    - For "change_in_working_capital": sum of ALL individual asset/liability change
      lines from CFS operating section. SIGNED per CFS convention.

    BALANCE SHEET RULES (when requested):
    - The balance sheet MUST balance: Total Assets = Total Liabilities + Total Equity.
    - "other_" catch-all fields must capture ALL unmapped line items.
    - After filling fields, verify the balance. Adjust catch-alls to close any gap.
    - "noncontrolling_interest_nonredeemable" and "noncontrolling_interest_redeemable"
      are memos, each copied from its own printed line (0 if the filing prints none).
      Do not combine them. Each is already inside another line; never add it to any total.

    If the user says "skip the balance sheet", set latest_balance_sheet to {{}}.""")


# ===========================================================================
# PASS 2: Non-Recurring Item Analysis — schema & prompt
# ===========================================================================

_NRI_SCHEMA = {
    "non_recurring_items": [
        {
            "year": "int — fiscal year the item affects",
            "description": "string — precise description of the item",
            "amount": "float — absolute dollar value (same units as financials)",
            "line_item": "string — Income Statement field where this item is embedded. Must be one of: cost_of_revenue | sga | rd_expense | depreciation_amortization | other_operating_expense | other_non_operating",
            "direction": "string — 'add_back' (one-time expense to remove) or 'remove' (one-time gain to strip)",
            "category": "string — restructuring | impairment | litigation | gain_loss_asset_sale | acquisition_costs | covid | other",
            "confidence": "string — high | medium | low",
            "source": "string — filing reference, e.g. 'Note 8 — Restructuring Charges'",
        }
    ]
}

_NRI_SCHEMA_STR = json.dumps(_NRI_SCHEMA, indent=2)

_NRI_SYSTEM_PROMPT = textwrap.dedent(f"""\
    You are a senior financial analyst specializing in earnings quality analysis.
    Your task is to identify NON-RECURRING, one-time, unusual, or infrequent items
    from a 10-K/10-Q filing that distort the company's recurring earnings.

    You will receive:
    1. The full 10-K/10-Q PDF filing (to read MD&A and Notes to Financial Statements)
    2. A summary of the extracted Income Statement (to anchor your findings)

    OUTPUT: Return ONLY a valid JSON object. No markdown fences, no explanation.
    The first character of your response must be {{.

    SCHEMA:
    {_NRI_SCHEMA_STR}

    WHAT TO LOOK FOR (read MD&A and Notes thoroughly):
    - Restructuring / severance / workforce reduction charges
    - Goodwill or asset impairment write-downs
    - Gains or losses on sale of assets, business units, or investments
    - Legal settlements, litigation charges or recoveries
    - Acquisition / integration / transaction costs
    - One-time regulatory charges or fines
    - Items explicitly called out in MD&A as non-recurring or unusual

    RULES:
    - For "line_item": use the EXACT field name from the Income Statement where
      the item is embedded: cost_of_revenue | sga | rd_expense |
      depreciation_amortization | other_operating_expense | other_non_operating
    - For "direction":
        "add_back" = one-time EXPENSE that inflated costs → remove to get clean earnings
        "remove"   = one-time GAIN that inflated income → strip to get clean earnings
    - Only flag items with clear evidence in the filing. Do NOT guess.
    - Use the provided I/S summary to verify amounts are plausible relative
      to the line item totals.
    - If no non-recurring items are found, return: {{"non_recurring_items": []}}""")


# ---------------------------------------------------------------------------
# Arithmetic validation
# ---------------------------------------------------------------------------

def _validate_extracted_data(
    llm_years: list[dict],
    fail_pct: float = 0.5,
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
# PDF reader — raw bytes for native LLM ingestion
# ---------------------------------------------------------------------------

def _read_pdf_bytes(path: str | Path) -> bytes:
    """Read raw PDF bytes for native document ingestion by the LLM."""
    pdf_path = Path(path)
    data = pdf_path.read_bytes()
    size_mb = len(data) / (1024 * 1024)
    print(f"  PDF: {pdf_path.name} ({size_mb:.1f} MB)")
    return data


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

# The Entra ID bearer-token provider, built once on first use.
#
# Cached because constructing DefaultAzureCredential probes several credential
# sources, and the provider returned by get_bearer_token_provider caches and
# refreshes the token itself. Rebuilding it per API call would repeat that probe —
# and an `az` subprocess — once per LLM call, six times in one valuation.
#
# This holds a credential *object*. It never holds, prints or logs a token value.
_ENTRA_TOKEN_PROVIDER: Callable[[], str] | None = None


def _entra_token_provider() -> Callable[[], str]:
    """Return the Entra ID bearer-token provider, building it on first use."""
    global _ENTRA_TOKEN_PROVIDER
    if _ENTRA_TOKEN_PROVIDER is None:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        _ENTRA_TOKEN_PROVIDER = get_bearer_token_provider(
            DefaultAzureCredential(), config.ENTRA_TOKEN_SCOPE,
        )
    return _ENTRA_TOKEN_PROVIDER


def _build_claude_client(resolution: ProviderResolution) -> anthropic.Anthropic:
    """Build the Anthropic client the resolution calls for.

    Foundry is a transport, not a provider: both branches below speak to Claude.
    The *decision* between them was already taken by `resolve_provider`; this
    function only reads the credential that decision named, and stops if it has
    gone missing since.
    """
    import anthropic

    # A session resolution labels figures already read and stored in a session
    # file. It names no credential, so building a client from it would fall
    # through to ANTHROPIC_API_KEY below and make a paid call under a label that
    # says no call was made. Stop instead.
    if resolution.transport == "claude-code-session":
        raise ValueError(
            "This ProviderResolution labels a Claude Code session file "
            f"({resolution.transport_label}). It carries no API credential and "
            "cannot be used to call the API.",
        )

    if resolution.credential == "entra-token":
        return anthropic.AnthropicFoundry(azure_ad_token_provider=_entra_token_provider())

    if resolution.credential == "foundry-api-key":
        api_key = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "ANTHROPIC_FOUNDRY_API_KEY resolved at startup but is empty now. "
                "Extraction cannot continue.",
            )
        return anthropic.AnthropicFoundry(api_key=api_key)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY resolved at startup but is empty now. "
            "Extraction cannot continue.",
        )
    return anthropic.Anthropic(api_key=api_key)


def _call_claude(
    system_prompt: str,
    user_prompt: str,
    resolution: ProviderResolution,
    pdf_bytes: bytes | None = None,
) -> tuple[str, int, int]:
    """Call Anthropic Claude. Returns (response_text, input_tokens, output_tokens)."""
    client = _build_claude_client(resolution)

    content: list[dict] = []
    if pdf_bytes:
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(pdf_bytes).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": user_prompt})

    response = client.messages.create(
        model=resolution.model,
        max_tokens=8096,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    # A response is a LIST of blocks, and the first one is not always the text.
    # claude-opus-5 emits a `thinking` block ahead of its answer on some requests,
    # and the old `response.content[0].text` raised AttributeError on those —
    # measured against this gateway, and one of the union-attr errors mypy already
    # reported on that line. Select the text blocks by type, and stop if there are
    # none rather than parsing an empty string into a statement full of zeros.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        kinds = ", ".join(block.type for block in response.content) or "none at all"
        raise ValueError(
            f"{resolution.model} returned no text block, so there is nothing to "
            f"parse. Block types received: {kinds}.",
        )

    # An answer cut off at the token ceiling is a partial answer. Parsing it would
    # produce a statement missing whatever the model had not written yet, and every
    # missing money field defaults to 0.0 downstream. Stop and name the cause.
    if response.stop_reason == "max_tokens":
        raise ValueError(
            f"{resolution.model} hit the {8096:,}-token output ceiling before "
            "finishing its response, so the extraction is incomplete. Re-run "
            "against fewer target years, or raise max_tokens in _call_claude.",
        )

    return "\n".join(text_blocks), response.usage.input_tokens, response.usage.output_tokens


def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    resolution: ProviderResolution,
    pdf_bytes: bytes | None = None,
    max_retries: int = 5,
) -> tuple[str, int, int]:
    """Call Google Gemini. Returns (response_text, input_tokens, output_tokens).

    Retries automatically on 429 (rate limit) and 503 (overloaded) errors
    with exponential backoff.
    """
    import re
    import time

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY resolved at startup but is empty now. "
            "Extraction cannot continue.",
        )
    model = resolution.model
    client = genai.Client(api_key=api_key)

    contents: list = []
    if pdf_bytes:
        contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
    contents.append(user_prompt)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=65536,
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            finish_reason = None
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
            text = response.text or ""
            in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            if finish_reason and finish_reason not in ("FinishReason.STOP", "STOP", "1"):
                print(f"  [WARN] Gemini finish_reason={finish_reason} — response may be truncated")
            return text, in_tok, out_tok
        except Exception as e:
            error_str = str(e)
            is_retryable = "429" in error_str or "503" in error_str or "RESOURCE_EXHAUSTED" in error_str or "UNAVAILABLE" in error_str
            if not is_retryable or attempt == max_retries:
                raise
            # Try to extract suggested retry delay from error message
            wait = 2 ** attempt  # default exponential backoff
            delay_match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
            if delay_match:
                wait = max(wait, float(delay_match.group(1)) + 1)
            print(f"  [RETRY {attempt}/{max_retries}] {e.__class__.__name__} — waiting {wait:.0f}s ...")
            time.sleep(wait)
    raise RuntimeError("Unreachable")


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    resolution: ProviderResolution,
    pdf_bytes: bytes | None = None,
) -> tuple[str, int, int]:
    """Route to the correct provider API."""
    if resolution.provider == "claude":
        return _call_claude(system_prompt, user_prompt, resolution, pdf_bytes=pdf_bytes)
    return _call_gemini(system_prompt, user_prompt, resolution, pdf_bytes=pdf_bytes)


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def _parse_financials_response(
    json_str: str,
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[str]]:
    """Parse Pass 1 JSON → FinancialStatements + validation errors."""
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
        delta_wc = float(yr.get("change_in_working_capital", 0))
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
    if bs_data and bs_data.get("year"):
        # The two noncontrolling interest lines, each as printed, read with no
        # fallback (rule 3; backlog item 1 is the reads that have one). An absent
        # or null key stays None, which means "not extracted";
        # analysis/dcf.py:total_noncontrolling_interest stops on it, naming the
        # key. A filing that prints no such line is answered with an explicit 0.
        # They are not added here: the sum is Python's, in that one function.
        nci_nonredeemable_raw = bs_data.get("noncontrolling_interest_nonredeemable")
        nci_redeemable_raw = bs_data.get("noncontrolling_interest_redeemable")
        nci_nonredeemable = (
            None if nci_nonredeemable_raw is None else float(nci_nonredeemable_raw)
        )
        nci_redeemable = None if nci_redeemable_raw is None else float(nci_redeemable_raw)
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
            noncontrolling_interest_nonredeemable=nci_nonredeemable,
            noncontrolling_interest_redeemable=nci_redeemable,
        ))

    financials = FinancialStatements(
        ticker=ticker or data.get("ticker", ""),
        company_name=company_name or data.get("company_name", ""),
        income_statements=sorted(income_statements, key=lambda x: x.year),
        balance_sheets=sorted(balance_sheets, key=lambda x: x.year),
        cash_flow_statements=sorted(cash_flow_statements, key=lambda x: x.year),
    )
    return financials, validation_errors


def _parse_nri_response(json_str: str) -> list[NonRecurringItem]:
    """Parse Pass 2 JSON → NonRecurringItem list.

    Three absences are distinguished from three empty-but-present values, because
    in each pair the two mean opposite things and the run cannot recover the
    difference later (rule 3):

    - `non_recurring_items` **absent** means the reply was never a Pass 2 answer,
      and nothing was read. `"non_recurring_items": []` means the model read the
      filing and found none — the prompt asks for exactly that (`:297`). The CLI
      and the result page both state, in words, what was withheld; on an absent
      key they would state "nothing was withheld" about a reply nobody parsed.
    - `confidence` is read with `[]`, not with a fallback to "high". The prompt
      asks for it on every item (`:255`), and `analysis/normalizer.py` now decides
      from it whether the item touches the statements at all. Defaulting an absent
      tag to the *strongest* value would hand that engine a certainty the model
      never expressed, and the adjustment would land at full weight with nothing
      saying so. Rule 3, in the optimistic direction.
    - `source` is the citation a reader follows to reverse an exclusion by hand
      (rule 4), so "the model cited no note" and "the key never arrived" must not
      collapse into the same empty string. An explicit `""` is accepted and is
      rendered `(none cited)`; an absent key stops.

    A KeyError here would name the field but not the item, so the loop raises a
    ValueError that names the year and the description as well — the two things a
    reader needs to find the item in the filing. The `.get` calls inside the
    messages below are deliberate: they are diagnostics printed about an item that
    is already known to be malformed, and a KeyError raised while building the
    message would hide the field that is actually missing.
    """
    data = json.loads(json_str)
    if "non_recurring_items" not in data:
        raise ValueError(
            "Pass 2 returned no 'non_recurring_items' field. An empty list is a "
            "valid answer and means the model found none; an absent field means "
            "the reply was not a Pass 2 answer and nothing was read. These are "
            f"not the same, so the run stops here. Keys returned: "
            f"{sorted(data)!r}"
        )
    items: list[NonRecurringItem] = []
    for item in data["non_recurring_items"]:
        if "confidence" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'confidence' "
                f"field: year {item.get('year')}, "
                f"{item.get('description')!r}. The prompt requires one of "
                f"high | medium | low on every item, and it is not assumed to "
                f"be 'high': analysis/normalizer.py decides from this tag "
                f"whether the item is applied to the financial statements."
            )
        if "source" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'source' field: "
                f"year {item.get('year')}, {item.get('description')!r}. The "
                f"prompt requires the filing reference on every item, and an "
                f"absent one is not read as an empty citation: the source is "
                f"what lets a reader find the note and apply a withheld item by "
                f"hand."
            )
        items.append(
            NonRecurringItem(
                year=int(item["year"]),
                description=item["description"],
                amount=float(item["amount"]),
                line_item=item["line_item"],
                direction=item["direction"],
                category=item["category"],
                confidence=item["confidence"],
                source=item["source"],
            )
        )
    return items


# ---------------------------------------------------------------------------
# User prompt builders
# ---------------------------------------------------------------------------

def _build_financials_prompt(
    target_years: list[int] | None = None,
    include_bs: bool = True,
) -> str:
    """Build the user prompt for Pass 1 (financial extraction).

    The PDF is sent as a native document attachment, not embedded in the prompt.
    """
    if target_years:
        year_str = ", ".join(str(y) for y in sorted(target_years))
        year_instruction = (
            f"Extract Income Statement and Cash Flow data for fiscal year(s): "
            f"{year_str} ONLY. Do NOT extract other years."
        )
    else:
        year_instruction = (
            "Extract Income Statement and Cash Flow data for ALL fiscal years "
            "present in the filing (typically 2-3 years)."
        )

    if include_bs:
        bs_instruction = "Also extract the latest balance sheet."
    else:
        bs_instruction = "Do NOT extract the balance sheet. Set latest_balance_sheet to {}."

    return (
        f"Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
        f"TARGET YEARS: {year_instruction}\n"
        f"BALANCE SHEET: {bs_instruction}"
    )


def _build_is_summary(
    financials: FinancialStatements,
    target_years: list[int] | None = None,
) -> str:
    """Format extracted I/S as context for Pass 2 (NRI analysis)."""
    years = target_years or financials.years
    lines = []
    for y in years:
        inc = financials.get_income_statement(y)
        if inc:
            # Show other_operating_expense as the LLM originally provided it
            # (before DA subtraction) so it matches what the NRI pass will reference
            other_opex_raw = inc.other_operating_expense + inc.depreciation_amortization
            lines.append(
                f"  FY{y}: Revenue={inc.revenue:,.0f}  "
                f"COGS={inc.cost_of_revenue:,.0f}  "
                f"SG&A={inc.sga:,.0f}  "
                f"R&D={inc.rd_expense:,.0f}  "
                f"D&A={inc.depreciation_amortization:,.0f}  "
                f"Other_OpEx={other_opex_raw:,.0f}  "
                f"EBIT={inc.ebit:,.0f}  "
                f"Other_NonOp={inc.other_non_operating:,.0f}"
            )
    return "\n".join(lines) if lines else "  (no data available)"


def _build_nri_prompt(
    is_summary: str,
    target_years: list[int] | None = None,
) -> str:
    """Build the user prompt for Pass 2 (NRI analysis).

    The PDF is sent as a native document attachment, not embedded in the prompt.
    """
    if target_years:
        year_str = ", ".join(str(y) for y in sorted(target_years))
        year_instruction = f"Analyze non-recurring items for fiscal year(s): {year_str}."
    else:
        year_instruction = "Analyze non-recurring items for ALL fiscal years in the filing."

    return (
        f"{year_instruction}\n\n"
        f"EXTRACTED INCOME STATEMENT (for reference — use to anchor your findings):\n"
        f"{is_summary}"
    )


def _pass1_prompt_pair(
    target_years: list[int] | None,
    include_bs: bool,
) -> tuple[str, str]:
    """The (system, user) prompt pair for Pass 1. The ONE place it is assembled.

    `_run_financials_pass` (route A) and `pass1_prompts` (route B) both call this,
    so the prompt the API receives and the prompt a session is shown cannot differ.
    """
    return _FINANCIALS_SYSTEM_PROMPT, _build_financials_prompt(target_years, include_bs)


def _pass2_prompt_pair(
    financials: FinancialStatements,
    target_years: list[int] | None,
) -> tuple[str, str]:
    """The (system, user) prompt pair for Pass 2. The ONE place it is assembled.

    `financials` is that filing's own Pass 1 result, before any merge: route A's
    `_run_nri_pass` receives exactly that, and the session route parses that
    filing's stored Pass 1 answer to get it.
    """
    is_summary = _build_is_summary(financials, target_years)
    return _NRI_SYSTEM_PROMPT, _build_nri_prompt(is_summary, target_years)


# ---------------------------------------------------------------------------
# Pass 1: Financial Statement Extraction (with retry)
# ---------------------------------------------------------------------------

def _run_financials_pass(
    pdf_bytes: bytes,
    ticker: str,
    company_name: str,
    resolution: ProviderResolution,
    target_years: list[int] | None = None,
    include_bs: bool = True,
    debug: bool = False,
) -> FinancialStatements:
    """Execute Pass 1: extract I/S, C/F, and optionally B/S."""
    # The same builder `pass1_prompts` calls, so the prompt sent here and the one
    # the session route prints for the same plan are one string, not two copies.
    system_prompt, user_prompt = _pass1_prompt_pair(target_years, include_bs)

    year_label = f"for {sorted(target_years)}" if target_years else "(all years)"
    bs_label = " + B/S" if include_bs else ""
    print(f"  [Pass 1] Extracting financials {year_label}{bs_label}...")

    raw, in_tok, out_tok = _call_llm(
        system_prompt, user_prompt, resolution,
        pdf_bytes=pdf_bytes,
    )
    if in_tok or out_tok:
        print(f"  [Pass 1] Tokens — input: {in_tok:,}  output: {out_tok:,}")

    if debug:
        print(f"\n{'='*65}\nPASS 1 RAW RESPONSE\n{'='*65}\n{raw}\n{'='*65}\n")

    # Parse + Validate + Retry loop
    MAX_RETRIES = 2
    json_str = _extract_json(raw)

    for attempt in range(1 + MAX_RETRIES):
        try:
            financials, val_errors = _parse_financials_response(
                json_str, ticker, company_name,
            )
        except json.JSONDecodeError as exc:
            ctx_start = max(0, exc.pos - 120)
            ctx_end = min(len(json_str), exc.pos + 120)
            print(f"\n  [Pass 1 JSON error] {exc}")
            print(f"  Context: ...{json_str[ctx_start:ctx_end]}...")

            if attempt >= MAX_RETRIES:
                raise
            print(f"  Retrying — asking {resolution.provider.upper()} to repair JSON...")
            fix_prompt = (
                "The following JSON is malformed. Return ONLY the corrected JSON "
                "object with no markdown fences and no additional text.\n\n"
                + json_str
            )
            raw2, _, _ = _call_llm(
                system_prompt, fix_prompt, resolution,
            )
            json_str = _extract_json(raw2)
            continue

        # Validation passed
        if not val_errors:
            return financials

        # Validation failed — feedback loop
        if attempt >= MAX_RETRIES:
            print(f"\n  [Pass 1 WARN] Validation errors remain after {MAX_RETRIES} retries:")
            for e in val_errors:
                print(f"    {e}")
            return financials

        print(f"\n  [Pass 1] Validation errors — sending feedback "
              f"(retry {attempt + 1}/{MAX_RETRIES})...")
        error_list = "\n".join(f"  - {e}" for e in val_errors)
        fix_prompt = (
            "The following JSON has arithmetic errors in the income statement.\n\n"
            "ERRORS:\n" + error_list + "\n\n"
            "Fix so these reconcile exactly:\n"
            "  gross_profit = revenue - cost_of_revenue\n"
            "  operating_income = gross_profit - sga - rd_expense - other_operating_expense\n"
            "  net_income = operating_income + interest_income - interest_expense "
            "+ other_non_operating - tax_expense\n\n"
            "Use ONLY numbers from the original filing. Return ONLY the corrected JSON.\n\n"
            + json_str
        )
        raw2, in2, out2 = _call_llm(
            system_prompt, fix_prompt, resolution,
        )
        if in2 or out2:
            print(f"  [Pass 1] Retry tokens — input: {in2:,}  output: {out2:,}")
        json_str = _extract_json(raw2)

    return financials


# ---------------------------------------------------------------------------
# Pass 2: Non-Recurring Item Analysis
# ---------------------------------------------------------------------------

def _run_nri_pass(
    pdf_bytes: bytes,
    financials: FinancialStatements,
    resolution: ProviderResolution,
    target_years: list[int] | None = None,
    debug: bool = False,
) -> list[NonRecurringItem]:
    """Execute Pass 2: analyze footnotes for non-recurring items.

    Receives the extracted FinancialStatements from Pass 1 so it can build
    an I/S summary as context for the LLM.
    """
    # The same builder `pass2_prompts` calls; see _run_financials_pass.
    system_prompt, user_prompt = _pass2_prompt_pair(financials, target_years)

    year_label = f"for {sorted(target_years)}" if target_years else ""
    print(f"  [Pass 2] Analyzing non-recurring items {year_label}...")

    raw, in_tok, out_tok = _call_llm(
        system_prompt, user_prompt, resolution,
        pdf_bytes=pdf_bytes,
    )
    if in_tok or out_tok:
        print(f"  [Pass 2] Tokens — input: {in_tok:,}  output: {out_tok:,}")

    if debug:
        print(f"\n{'='*65}\nPASS 2 RAW RESPONSE\n{'='*65}\n{raw}\n{'='*65}\n")

    json_str = _extract_json(raw)

    try:
        nri = _parse_nri_response(json_str)
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"  [Pass 2 WARN] Failed to parse NRI response: {exc}")
        print("  Retrying once...")
        fix_prompt = (
            "The following JSON is malformed. Return ONLY the corrected JSON object "
            "with no markdown fences.\n\n" + json_str
        )
        raw2, _, _ = _call_llm(
            system_prompt, fix_prompt, resolution,
        )
        try:
            nri = _parse_nri_response(_extract_json(raw2))
        except Exception:
            print("  [Pass 2 WARN] NRI parsing failed after retry — returning empty list")
            return []

    if nri:
        print(f"  [Pass 2] Found {len(nri)} non-recurring item(s):")
        for item in nri:
            sign = "+" if item.direction == "add_back" else "-"
            print(f"    {item.year} {sign}{item.amount:,.0f}M on "
                  f"{item.line_item} — {item.description[:60]}")
    else:
        print("  [Pass 2] No non-recurring items identified")

    return nri


# ---------------------------------------------------------------------------
# Provider, transport and credential resolution
# ---------------------------------------------------------------------------

# The stop when provider="claude" and no credential of any kind resolves.
# It names BOTH remedies, because either one alone is enough and a reader with no
# Anthropic account needs to be told the second one exists.
_NO_CLAUDE_CREDENTIAL = (
    "No Anthropic credential resolved, so extraction cannot start. "
    "Either remedy is sufficient:\n"
    "  (1) Set ANTHROPIC_API_KEY in .env or the system environment, to use the "
    "public Anthropic API; or\n"
    "  (2) Set ANTHROPIC_FOUNDRY_BASE_URL (or ANTHROPIC_FOUNDRY_RESOURCE) to a "
    "Microsoft Foundry gateway and sign in with `az login`, so "
    "DefaultAzureCredential can issue an Entra ID token for scope "
    f"{config.ENTRA_TOKEN_SCOPE}. A Foundry gateway also accepts "
    "ANTHROPIC_FOUNDRY_API_KEY instead of `az login`.\n"
    "See docs/8-build/environment.md section 3."
)


def _resolve_model(provider: Provider, model: str | None) -> str:
    """Resolve the model ID. An explicitly empty model stops rather than defaulting."""
    if model is None:
        return _DEFAULT_MODELS[provider]
    if not model.strip():
        raise ValueError(
            "model was given as an empty string. Pass a model ID, or omit it "
            f"entirely to use this provider's default ({_DEFAULT_MODELS[provider]}).",
        )
    return model


def _foundry_endpoint_label() -> str:
    """Name the Foundry endpoint for display. A hostname, never a credential.

    `.hostname`, not `.netloc`: netloc carries the userinfo of a URL, so a base URL
    written as `https://user:secret@gw.example.net/x` would put `user:secret` on
    stdout and into the rendered result page. `.hostname` returns the host alone
    (and drops the port, which names nothing).
    """
    base_url = os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL", "").strip()
    if base_url:
        host = urlsplit(base_url).hostname
        if not host:
            raise ValueError(
                f"ANTHROPIC_FOUNDRY_BASE_URL is set but is not a URL with a host: "
                f"{base_url!r}",
            )
        return host
    resource = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "").strip()
    if resource:
        return f"{resource}.services.ai.azure.com"
    raise ValueError(
        "_foundry_endpoint_label called with no Foundry gateway configured.",
    )


def _resolve_claude(model: str) -> ProviderResolution:
    """Choose the transport and the credential for Claude, or stop naming both remedies."""
    base_url = os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL", "").strip()
    resource = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "").strip()

    if base_url and resource:
        raise ValueError(
            "ANTHROPIC_FOUNDRY_BASE_URL and ANTHROPIC_FOUNDRY_RESOURCE are both "
            "set. The Anthropic SDK treats them as mutually exclusive. Unset one.",
        )

    if base_url or resource:
        endpoint = _foundry_endpoint_label()
        transport_label = f"Microsoft Foundry gateway ({endpoint})"

        if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "").strip():
            return ProviderResolution(
                provider="claude",
                model=model,
                transport="foundry",
                transport_label=transport_label,
                credential="foundry-api-key",
                credential_source="ANTHROPIC_FOUNDRY_API_KEY (environment)",
            )

        # No Foundry key, so an Entra ID token. Prove the library is importable
        # here rather than letting the first API call fail with an ImportError
        # that names neither the cause nor the remedy.
        try:
            import azure.identity  # noqa: F401
        except ModuleNotFoundError as exc:
            raise ValueError(
                f"A Microsoft Foundry gateway is configured ({endpoint}) and no "
                "ANTHROPIC_FOUNDRY_API_KEY is set, so an Entra ID token is "
                "required — but azure-identity is not installed. Run "
                "`pip install -r requirements.txt`, then `az login`. "
                "Alternatively set ANTHROPIC_API_KEY and unset the Foundry "
                "variables to use the public Anthropic API.",
            ) from exc

        return ProviderResolution(
            provider="claude",
            model=model,
            transport="foundry",
            transport_label=transport_label,
            credential="entra-token",
            credential_source=(
                f"Entra ID token via DefaultAzureCredential (`az login`), scope "
                f"{config.ENTRA_TOKEN_SCOPE}"
            ),
        )

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return ProviderResolution(
            provider="claude",
            model=model,
            transport="anthropic-direct",
            transport_label="Anthropic public API (api.anthropic.com)",
            credential="anthropic-api-key",
            credential_source="ANTHROPIC_API_KEY (environment)",
        )

    raise ValueError(_NO_CLAUDE_CREDENTIAL)


def _resolve_gemini(model: str) -> ProviderResolution:
    """Choose the transport and the credential for Gemini, or stop naming the remedy."""
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise ValueError(
            "GEMINI_API_KEY is not set, so extraction cannot start with "
            "provider='gemini'. Add it to .env or the system environment, or use "
            f"provider='{config.DEFAULT_EXTRACTION_PROVIDER}'.",
        )
    return ProviderResolution(
        provider="gemini",
        model=model,
        transport="gemini-direct",
        transport_label="Google Gemini API (generativelanguage.googleapis.com)",
        credential="gemini-api-key",
        credential_source="GEMINI_API_KEY (environment)",
    )


def resolve_provider(
    provider: Provider,
    model: str | None,
) -> ProviderResolution:
    """Resolve provider, model, transport and credential, or stop.

    Reads the environment only. It acquires no token and makes no network call, so
    it is cheap enough to call from a request handler purely to label a result page.

    Raises ValueError, naming the field and the remedy, when no credential of any
    kind resolves (rule 3). A missing credential must never produce a client that
    fails later with an unrelated message.
    """
    if provider not in ("claude", "gemini"):
        raise ValueError(f"provider must be 'claude' or 'gemini', got '{provider}'")

    resolved_model = _resolve_model(provider, model)

    if provider == "claude":
        return _resolve_claude(resolved_model)
    return _resolve_gemini(resolved_model)


def describe_resolution(resolution: ProviderResolution) -> str:
    """One line naming who read the filing, over what, on whose credential (rule 6)."""
    return (
        f"Provider: {resolution.provider.upper()}  |  "
        f"Model: {resolution.model}  |  "
        f"Transport: {resolution.transport_label}  |  "
        f"Credential: {resolution.credential_source}"
    )


# ===========================================================================
# Shared by both extraction routes: the plan, the merge, the prompts, the parsers
# ===========================================================================
#
# Route A (this file's API calls) and route B (a Claude Code session writing a
# session file, ingestion/session_extraction.py) meet here. Each job below has
# exactly one implementation, and both routes call it, so a fix to the plan or the
# merge cannot land in one route and miss the other (the shape of backlog item 7).

@dataclass(frozen=True)
class FilingPlan:
    """What one filing is asked for: which years, and whether its balance sheet.

    `target_years` is None for "every year the filing presents". A tuple, not a
    list, so the plan is hashable and cannot be mutated after `plan_filings`
    produced it.
    """

    fiscal_year: int
    pdf_path: str
    target_years: tuple[int, ...] | None
    include_bs: bool


def plan_filings(filings: list[tuple[int, str | Path]]) -> list[FilingPlan]:
    """Decide which years and which balance sheet come from which filing.

    One filing: every year it presents, and its balance sheet. Several, sorted
    ascending by fiscal year: the oldest gives every year it presents and no
    balance sheet, each middle one gives its own year only and no balance sheet,
    and the newest gives its own year and the balance sheet.

    Raises:
        ValueError: when `filings` is empty.
    """
    if not filings:
        raise ValueError("filings list is empty")

    if len(filings) == 1:
        fiscal_year, pdf_path = filings[0]
        return [FilingPlan(
            fiscal_year=fiscal_year,
            pdf_path=str(pdf_path),
            target_years=None,
            include_bs=True,
        )]

    filings_sorted = sorted(filings, key=lambda x: x[0])  # ascending by year
    oldest_year = filings_sorted[0][0]
    newest_year = filings_sorted[-1][0]
    return [
        FilingPlan(
            fiscal_year=fiscal_year,
            pdf_path=str(pdf_path),
            target_years=None if fiscal_year == oldest_year else (fiscal_year,),
            include_bs=fiscal_year == newest_year,
        )
        for fiscal_year, pdf_path in filings_sorted
    ]


def _plan_target_years(plan: FilingPlan) -> list[int] | None:
    """The plan's target years in the list form the prompt builders take."""
    if plan.target_years is None:
        return None
    return list(plan.target_years)


def merge_filing_extractions(
    extractions: list[tuple[FilingPlan, FinancialStatements, list[NonRecurringItem]]],
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Merge per-filing results into one set of statements and one item list.

    `extractions` is in plan order (ascending fiscal year), as `plan_filings`
    returns it. For each statement year, the statement from the filing whose
    `fiscal_year` equals that year is preferred; otherwise the first one seen is
    kept. Non-recurring items are deduplicated on (year, amount, direction),
    first seen kept.
    """
    all_income: dict[int, IncomeStatement] = {}
    all_balance: dict[int, BalanceSheet] = {}
    all_cashflow: dict[int, CashFlowStatement] = {}
    all_nri: list[NonRecurringItem] = []
    nri_keys: set[tuple[int, float, str]] = set()

    for plan, fin, nri in extractions:
        fiscal_year = plan.fiscal_year

        # Merge: prefer the "primary" filing (where fiscal_year matches the year)
        for income in fin.income_statements:
            y = income.year
            if y not in all_income or y == fiscal_year:
                all_income[y] = income
        for balance in fin.balance_sheets:
            y = balance.year
            if y not in all_balance or y == fiscal_year:
                all_balance[y] = balance
        for cashflow in fin.cash_flow_statements:
            y = cashflow.year
            if y not in all_cashflow or y == fiscal_year:
                all_cashflow[y] = cashflow

        # Dedupe NRIs by (year, amount, direction)
        for item in nri:
            key = (item.year, item.amount, item.direction)
            if key not in nri_keys:
                all_nri.append(item)
                nri_keys.add(key)

    merged = FinancialStatements(
        ticker=ticker,
        company_name=company_name,
        income_statements=sorted(all_income.values(), key=lambda x: x.year),
        balance_sheets=sorted(all_balance.values(), key=lambda x: x.year),
        cash_flow_statements=sorted(all_cashflow.values(), key=lambda x: x.year),
    )
    return merged, all_nri

def pass1_prompts(plan: FilingPlan) -> tuple[str, str]:
    """The (system, user) prompt route A sends for this plan's Pass 1."""
    return _pass1_prompt_pair(_plan_target_years(plan), plan.include_bs)


def pass2_prompts(
    plan: FilingPlan,
    financials: FinancialStatements,
) -> tuple[str, str]:
    """The (system, user) prompt route A sends for this plan's Pass 2.

    `financials` must be this filing's own Pass 1 result, unmerged.
    """
    return _pass2_prompt_pair(financials, _plan_target_years(plan))


def parse_pass1(
    json_str: str,
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[str]]:
    """Parse a Pass 1 answer into statements plus arithmetic validation errors."""
    return _parse_financials_response(json_str, ticker, company_name)


def parse_pass2(json_str: str) -> list[NonRecurringItem]:
    """Parse a Pass 2 answer into non-recurring items."""
    return _parse_nri_response(json_str)


# ===========================================================================
# Public API
# ===========================================================================

def extract_financials(
    pdf_path: str | Path,
    ticker: str = "",
    company_name: str = "",
    provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER,
    model: str | None = None,
    target_years: list[int] | None = None,
    include_bs: bool = True,
    debug: bool = False,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Extract financial data from a single 10-K/10-Q PDF using two LLM passes.

    The raw PDF is sent directly to the LLM for native document ingestion
    (no intermediate text extraction).

    Pass 1: Extract I/S + C/F (+ optional B/S) for target years.
    Pass 2: Analyze footnotes for non-recurring items, using Pass 1 I/S as context.

    Args:
        pdf_path:      Path to the PDF filing.
        ticker:        Stock ticker.
        company_name:  Company name.
        provider:      "claude" or "gemini". Defaults to
                       config.DEFAULT_EXTRACTION_PROVIDER.
        model:         Override model ID.
        target_years:  Specific fiscal years to extract. None = all years in filing.
        include_bs:    Whether to extract the balance sheet (default True).
        debug:         Print raw LLM responses.

    Returns:
        (FinancialStatements, list[NonRecurringItem])
    """
    resolution = resolve_provider(provider, model)

    # Rule 6: which model read this filing, over which transport, on whose
    # credential, is an assumption about every figure below. Say it out loud.
    print(f"\n  {describe_resolution(resolution)}")
    pdf_bytes = _read_pdf_bytes(pdf_path)

    # Pass 1: Financial data extraction
    financials = _run_financials_pass(
        pdf_bytes, ticker, company_name, resolution,
        target_years=target_years, include_bs=include_bs, debug=debug,
    )

    # Pass 2: Non-recurring item analysis (receives Pass 1 I/S as context)
    nri = _run_nri_pass(
        pdf_bytes, financials, resolution,
        target_years=target_years, debug=debug,
    )

    return financials, nri


def extract_multi_year(
    filings: list[tuple[int, str | Path]],
    ticker: str = "",
    company_name: str = "",
    provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER,
    model: str | None = None,
    debug: bool = False,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Smart multi-PDF extraction with year-targeting.

    Raw PDFs are sent directly to the LLM for native document ingestion.

    Minimizes redundant LLM calls by extracting each year from only one filing:
      - Oldest filing: extract ALL years (picks up comparative years like Y-1, Y-2)
      - Other filings: extract ONLY the primary fiscal year
      - Balance sheet: extracted only from the most recent filing

    Example:
        filings = [(2025, "10K_2025.pdf"), (2024, "10K_2024.pdf"), (2023, "10K_2023.pdf")]
        → 2023 10-K: extract all years (2023, 2022, 2021)  — no B/S
        → 2024 10-K: extract [2024] only                   — no B/S
        → 2025 10-K: extract [2025] only                   — with B/S

    Args:
        filings:       List of (fiscal_year, pdf_path) tuples.
        ticker:        Stock ticker.
        company_name:  Company name.
        provider:      "claude" or "gemini". Defaults to
                       config.DEFAULT_EXTRACTION_PROVIDER — the same default as
                       extract_financials, so the number of PDFs uploaded cannot
                       change which model reads them.
        model:         Override model ID.
        debug:         Print raw LLM responses.

    Returns:
        Merged (FinancialStatements, list[NonRecurringItem]) across all filings.
    """
    plans = plan_filings(filings)  # raises on an empty list

    if len(plans) == 1:
        # Single filing — just extract everything. Deliberately NOT passed through
        # merge_filing_extractions: the merge re-sorts and replaces the parsed
        # ticker, and a single filing's result is returned exactly as parsed.
        plan = plans[0]
        return extract_financials(
            pdf_path=plan.pdf_path,
            ticker=ticker, company_name=company_name,
            provider=provider, model=model,
            target_years=_plan_target_years(plan), include_bs=plan.include_bs,
            debug=debug,
        )

    # Print extraction plan
    print(f"\n{'='*65}")
    print(f"MULTI-YEAR EXTRACTION PLAN — {ticker or 'Unknown'}")
    print(f"{'='*65}")
    for plan in plans:
        if plan.target_years is None:
            plan_text = "all years (oldest filing)"
        else:
            plan_text = f"year {plan.fiscal_year} only"
        bs = " + B/S" if plan.include_bs else ""
        print(f"  {Path(plan.pdf_path).name} -> {plan_text}{bs}")
    print(f"{'='*65}")

    # Execute extraction for each filing, in plan order
    extractions: list[tuple[FilingPlan, FinancialStatements, list[NonRecurringItem]]] = []
    for plan in plans:
        print(f"\n{'='*65}")
        print(f"EXTRACTING: {Path(plan.pdf_path).name}  (fiscal {plan.fiscal_year})")
        print(f"{'='*65}")

        fin, nri = extract_financials(
            pdf_path=plan.pdf_path,
            ticker=ticker,
            company_name=company_name,
            provider=provider,
            model=model,
            target_years=_plan_target_years(plan),
            include_bs=plan.include_bs,
            debug=debug,
        )
        extractions.append((plan, fin, nri))

    merged, all_nri = merge_filing_extractions(extractions, ticker, company_name)

    print(f"\n{'='*65}")
    print(f"MERGED: {len(merged.years)} years {merged.years}, "
          f"{len(all_nri)} non-recurring item(s)")
    print(f"{'='*65}")

    return merged, all_nri
