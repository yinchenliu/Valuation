"""Route B: an extraction read in a Claude Code session and stored in a session file.

Route A (`ingestion/claude_extractor.py`) sends each 10-K to the model over an API,
twice per filing. Route B has a Claude Code session read the same PDF in the chat and
write the same two JSON answers into a **session file**. The pipeline then reads that
file instead of calling the API.

The two routes meet at the parser. This module calls, and never copies:

    plan_filings              which years and which balance sheet from which filing
    pass1_prompts / pass2_prompts   the prompts route A sends for that plan
    parse_pass1 / parse_pass2       route A's parsers
    printed_line_page_failures      route A's page check: each printed line
                                    looked up on the page it cites
    unit_statement_page_failures    route A's unit check: each printed unit
                                    statement looked up on the page it cites
    filing_units / convert_filing_to_millions
                              the scales read from the unit statements, and
                              route A's conversion of each filing to millions
    merge_filing_extractions  route A's merge

so the same two JSON answers give the same `FinancialStatements` and the same
`NonRecurringItem` list by either route.

**This module holds no model client, no prompt text and no credential.**
`docs/2-rules/llm-boundary.md`: `claude_extractor.py` is the only file that may.

The file format, `session-extraction-v3`:

    {
      "format": "session-extraction-v3",
      "ticker": "CMG",
      "company_name": "Chipotle Mexican Grill, Inc.",
      "extracted_by": {"model": null, "tool": "Claude Code", "date": null},
      "filings": [
        {
          "fiscal_year": 2023,
          "pdf_path": "/absolute/path/to/the.pdf",
          "pdf_sha256": "...",
          "size_bytes": 1234567,
          "target_years": null,
          "include_bs": false,
          "pages_read": {"pass1": [], "pass2": []},
          "pass1": null,
          "pass2": null
        }
      ]
    }

`pass1` and `pass2` hold exactly the JSON objects route A parses. In `pass1` every
figure is a list of the printed lines that make it up, each
`{"label": ..., "value": ..., "page": ...}`, and Python adds them
(`figure_from_printed_lines`); `[]` means the filing prints no such row. `pass1`
also carries two printed unit statements, each `{"printed": ..., "page": ...}`:
`units` for the money figures and `share_units` for the diluted share count. Each is
looked up on its page (the loader stops on one not found), Python reads the scale
word in it, and each filing is converted to millions once, after its Pass 2 and
before the merge. Pass 2's items each carry `page` (the 1-based page the figure
is printed on) and `units` (the words that state its unit, and their page); Python
reads the scale and converts each item. A `session-extraction-v1` file, which held
one figure per field, is refused by name: it must be extracted again. A
`session-extraction-v2` file, whose `units` is a free string and which has no
`share_units`, is refused by name too: run the `extract-filing` skill again, or add
the two keys from the filing's printed unit statement. A `session-extraction-v3`
file, whose Pass 2 items lack `page` and `units`, is refused by name: run the
skill again, or add `page` and `units` to each item. `pages_read` is a locator (1-based
PDF pages); it is recorded and printed, never computed from.
`extracted_by.model` is the model ID the session declares; it cannot be verified and
is printed as declared. `extracted_by.tool` and `extracted_by.date` are a record for a
human reader and are not read by this module.

Subcommands, run as `python -m ingestion.session_extraction <command>`:

    plan   <pdf args> -t TICKER [-n NAME] -o FILE [--force]
    locate FILE --filing N
    text   FILE --filing N --pages A-B
    prompt FILE --filing N --pass 1|2
    check  FILE

`--filing N` is the 0-based index into the file's `filings` array.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.claude_extractor import (
    _NRI_SCHEMA,
    FilingPlan,
    FilingUnits,
    ProviderResolution,
    convert_filing_to_millions,
    describe_resolution,
    filing_units,
    merge_filing_extractions,
    parse_pass1,
    parse_pass2,
    pass1_problems,
    pass1_prompts,
    pass2_page_failures,
    pass2_prompts,
    plan_filings,
    printed_line_page_failures,
    unit_statement_page_failures,
)
from ingestion.filings import fingerprint_filings, parse_pdf_args
from models.financial_statements import FinancialStatements, NonRecurringItem

SESSION_FORMAT = "session-extraction-v4"

# The format before P11a. Its Pass 1 holds one figure per field, and some of those
# figures were sums the session worked out; v2 holds the printed lines and Python
# adds them. A v1 file is refused by name rather than read, because its figures
# cannot be turned back into the lines they came from.
_SESSION_FORMAT_V1 = "session-extraction-v1"

# The format before P14a. Its `pass1.units` is a free string no code read, and it has
# no `share_units`, so a filing printed in thousands was read as millions (backlog
# item 44). Refused by name: its figures are fine, and the two unit statements can
# be added by hand from the filing.
_SESSION_FORMAT_V2 = "session-extraction-v2"

# The format before P14b. Each Pass 2 item held an amount converted by the model,
# with no page and no printed unit words (backlog item 77). Refused by name: run
# the extract-filing skill again, or add to each Pass 2 item 'page' and 'units'
# from the page where its figure is printed, and write 'amount' as printed.
_SESSION_FORMAT_V3 = "session-extraction-v3"

# Every key a Pass 2 item must carry, read from the schema route A's Pass 2 prompt is
# built from, so the two cannot drift. `claude_extractor.py` exports no public name
# for it, as it does for Pass 1 (PASS1_YEAR_FIELDS); this unit may not edit that file,
# so the private name is imported. The P9d entry asks for a public one.
_PASS2_ITEM_FIELDS: tuple[str, ...] = tuple(_NRI_SCHEMA["non_recurring_items"][0])

# The widest page range `text` prints in one call. A 10-K runs to 100-200 pages; a
# session that loads all of them by accident spends its context on boilerplate.
MAX_TEXT_PAGES = 20

# Statement titles `locate` searches for. A label and a pattern: a lookup of data,
# not of behaviour.
_STATEMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "income statement (income / operations / earnings)",
        r"statements?\s+of\s+(?:consolidated\s+)?(?:income|operations|earnings)",
    ),
    (
        "balance sheet",
        r"balance\s+sheets?|statements?\s+of\s+financial\s+position",
    ),
    (
        "cash flow statement",
        r"statements?\s+of\s+cash\s+flows?",
    ),
)

# Non-recurring keywords `locate` searches for, with the same shape.
_NRI_PATTERNS: tuple[tuple[str, str], ...] = (
    ("restructuring", r"restructuring"),
    ("impairment", r"impairments?"),
    ("litigation", r"litigation"),
    ("settlement", r"settlements?"),
    (
        "gain or loss on sale",
        (r"(?:gains?|loss(?:es)?|\(gain\)|\(loss\))\s+(?:(?:gain|loss)\s+)?"
         r"on\s+(?:the\s+)?(?:sales?|disposals?|dispositions?)"),
    ),
    ("divestiture", r"divestitures?"),
    ("severance", r"severance"),
    ("acquisition-related", r"acquisition[-\s]+related"),
    ("write-down", r"write[-\s]?downs?"),
)

# A statement page is told apart from a page that merely mentions the statement by
# a TITLE LINE: a line that holds the title, no digit, and at most this many
# characters. The digit rule drops table-of-contents entries ("... of Income 52");
# the length rule drops sentences in the auditor's report and the notes. Measured on
# the Walmart 2026 10-K, which prints two or three printed pages per PDF page, so a
# title is not always at the top of a PDF page.
_TITLE_LINE_MAX_CHARS = 80


# ===========================================================================
# What the loader returns
# ===========================================================================

@dataclass(frozen=True)
class SessionFiling:
    """One filing of a session file, as verified against the PDF on disk."""

    index: int
    plan: FilingPlan
    pdf_sha256: str
    size_bytes: int
    pages_pass1: tuple[int, ...]
    pages_pass2: tuple[int, ...]
    # The two printed unit statements, each confirmed on its page, and the scale
    # Python read in each: what this filing's figures were converted from (P14a).
    units: FilingUnits


@dataclass(frozen=True)
class SessionExtraction:
    """A session file, checked, parsed and merged exactly as route A merges.

    `validation_errors` are route A's failed checks: printed subtotals and totals
    against Python's sums of the lines, and each printed line looked up on the
    page it cites, in the PDF. They are returned, not raised: route A keeps its figures with a warning after its last
    retry, and both routes must reach the same result from the same JSON.
    """

    financials: FinancialStatements
    non_recurring: list[NonRecurringItem]
    resolution: ProviderResolution
    validation_errors: list[str]
    session_file: str
    filings: tuple[SessionFiling, ...]


# ===========================================================================
# Reading the file
# ===========================================================================

def _is_int(value: object) -> bool:
    """True for a JSON integer. A bool is not one, although Python says it is."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    """True for a finite JSON number. `json` accepts NaN and Infinity; we do not."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _read_session_json(path: Path) -> dict[str, Any]:
    """Read the file and check its format marker, or stop naming the file.

    Every stop in this module raises ValueError, including a value of the wrong JSON
    type, where ruff's TRY004 would prefer TypeError. ValueError is the loader's
    stated contract (one exception type for "this session file cannot be used"),
    and a wrongly-typed value in a data file is bad input, not a programming error.
    """
    if not path.is_file():
        raise ValueError(f"{path}: session file not found.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc}).") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the top level must be a JSON object.")  # noqa: TRY004 — see _read_session_json
    if "format" not in data:
        raise ValueError(
            f"{path}: key 'format' is absent. Expected {SESSION_FORMAT!r}.",
        )
    if data["format"] == _SESSION_FORMAT_V1:
        raise ValueError(
            f"{path}: format is {_SESSION_FORMAT_V1!r}, and this reader understands "
            f"{SESSION_FORMAT!r} only. The Pass 1 shape changed: in "
            f"{SESSION_FORMAT!r} every figure is the list of printed lines that make "
            "it up (label, value, page), and Python adds them, where a v1 file "
            "holds one figure per field, some of them sums the session worked out. "
            "A v1 file cannot be converted. Extract the filing again in the new "
            "shape: run `plan`, then `prompt --pass 1` prints the schema.",
        )
    if data["format"] == _SESSION_FORMAT_V2:
        raise ValueError(
            f"{path}: format is {_SESSION_FORMAT_V2!r}, and this reader understands "
            f"{SESSION_FORMAT!r} only. The Pass 1 shape changed: 'units' is now the "
            "statement of the unit of the money figures exactly as printed, with its "
            'page, {"printed": ..., "page": ...}, where v2 held a free string; and '
            "'share_units' is new, the same shape, for the unit of the diluted share "
            "count. Python reads the scale word in each and converts every figure to "
            "millions. Remedy: run the extract-filing skill again, or add the two keys "
            "to each filing's pass1 from the filing's printed unit statement (usually "
            "just under the income statement's title; if one statement covers both, "
            "'share_units' copies it with its page), then set 'format' to "
            f"{SESSION_FORMAT!r}.",
        )
    if data["format"] == _SESSION_FORMAT_V3:
        raise ValueError(
            f"{path}: format is {_SESSION_FORMAT_V3!r}, and this reader understands "
            f"{SESSION_FORMAT!r} only. The Pass 2 shape changed: each non-recurring item "
            "now carries 'page' (the 1-based PDF page the figure is printed on) and "
            "'units' (the words printed that state its unit and their page, "
            '{"printed": ..., "page": ...}), and \'amount\' is copied as printed rather '
            "than converted by the model. Python reads the scale word and converts. "
            "Remedy: run the extract-filing skill again, or add to each Pass 2 item 'page' "
            "and 'units' from the page where its figure is printed, and write 'amount' "
            f"as printed, then set 'format' to {SESSION_FORMAT!r}."
        )
    if data["format"] != SESSION_FORMAT:
        raise ValueError(
            f"{path}: format is {data['format']!r}; this reader understands "
            f"{SESSION_FORMAT!r} only.",
        )
    return data


def _read_identity(data: dict[str, Any], path: Path) -> tuple[str, str]:
    """The ticker and company name. The ticker must be a non-empty string.

    The company name must be present and a string. It may be empty, exactly as
    route A's `company_name` may be: `parse_pass1` then takes the name the Pass 1
    answer gives, which is the same thing route A does with the same input.
    """
    if "ticker" not in data:
        raise ValueError(f"{path}: key 'ticker' is absent.")
    ticker = data["ticker"]
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"{path}: 'ticker' must be a non-empty string, got {ticker!r}.")
    if "company_name" not in data:
        raise ValueError(f"{path}: key 'company_name' is absent.")
    company_name = data["company_name"]
    if not isinstance(company_name, str):
        raise ValueError(  # noqa: TRY004 — see _read_session_json
            f"{path}: 'company_name' must be a string, got {company_name!r}.",
        )
    return ticker, company_name


def _read_model(data: dict[str, Any], path: Path) -> str:
    """The model ID the session declares. Required: it labels every figure (rule 6)."""
    if "extracted_by" not in data:
        raise ValueError(f"{path}: key 'extracted_by' is absent.")
    extracted_by = data["extracted_by"]
    if not isinstance(extracted_by, dict):
        raise ValueError(f"{path}: 'extracted_by' must be a JSON object.")  # noqa: TRY004 — see _read_session_json
    if "model" not in extracted_by:
        raise ValueError(f"{path}: key 'extracted_by.model' is absent.")
    model = extracted_by["model"]
    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            f"{path}: 'extracted_by.model' is {model!r}. Set it to the model ID "
            "of the session that read the filings. It is printed beside every "
            "figure as the model that read them, so it is not left blank.",
        )
    return model


def _filing_label(path: Path, index: int, entry: dict[str, Any]) -> str:
    """'<file>: filings[i] (<pdf name>)' — the prefix of every per-filing message."""
    pdf_path = entry.get("pdf_path")  # a diagnostic label only; checked below
    name = Path(pdf_path).name if isinstance(pdf_path, str) else "pdf_path missing"
    return f"{path}: filings[{index}] ({name})"


def _session_plans(
    data: dict[str, Any], path: Path,
) -> list[tuple[FilingPlan, dict[str, Any]]]:
    """Each filing's plan, rebuilt with `plan_filings` and checked against the file.

    The plan is not taken from the file on trust. `plan_filings` is the one place
    the routing is decided, so it is re-run here over the file's (fiscal_year,
    pdf_path) pairs, and every recorded `target_years` and `include_bs` must equal
    what it returns, in the same order. A hand-edited plan would otherwise make
    route B merge differently from route A on the same filings.
    """
    if "filings" not in data:
        raise ValueError(f"{path}: key 'filings' is absent.")
    entries = data["filings"]
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: 'filings' must be a non-empty list.")

    pairs: list[tuple[int, str | Path]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: filings[{index}] must be a JSON object.")  # noqa: TRY004 — see _read_session_json
        where = _filing_label(path, index, entry)
        for key in ("fiscal_year", "pdf_path", "target_years", "include_bs"):
            if key not in entry:
                raise ValueError(f"{where}: key '{key}' is absent.")
        if not _is_int(entry["fiscal_year"]):
            raise ValueError(
                f"{where}: 'fiscal_year' must be an integer, got "
                f"{entry['fiscal_year']!r}.",
            )
        if len(entries) > 1 and entry["fiscal_year"] <= 0:
            raise ValueError(
                f"{where}: 'fiscal_year' is {entry['fiscal_year']}. With more than "
                "one filing every filing needs its fiscal year, because the plan "
                "routes years by it.",
            )
        if not isinstance(entry["pdf_path"], str) or not entry["pdf_path"]:
            raise ValueError(f"{where}: 'pdf_path' must be a non-empty string.")
        pairs.append((entry["fiscal_year"], entry["pdf_path"]))

    plans = plan_filings(pairs)
    result: list[tuple[FilingPlan, dict[str, Any]]] = []
    for index, (plan, entry) in enumerate(zip(plans, entries, strict=True)):
        where = _filing_label(path, index, entry)
        if (plan.fiscal_year, plan.pdf_path) != (entry["fiscal_year"], entry["pdf_path"]):
            raise ValueError(
                f"{where}: the filings are not in plan order. plan_filings puts "
                f"fiscal {plan.fiscal_year} ({Path(plan.pdf_path).name}) at index "
                f"{index}. Re-run `plan` rather than reordering by hand.",
            )
        recorded_years = entry["target_years"]
        if recorded_years is not None and (
            not isinstance(recorded_years, list)
            or not all(_is_int(y) for y in recorded_years)
        ):
            raise ValueError(
                f"{where}: 'target_years' must be null or a list of integers, got "
                f"{recorded_years!r}.",
            )
        planned_years = None if plan.target_years is None else list(plan.target_years)
        if recorded_years != planned_years:
            raise ValueError(
                f"{where}: 'target_years' is {recorded_years!r} but plan_filings "
                f"gives {planned_years!r}. The plan is route A's plan and is not "
                "edited by hand.",
            )
        if not isinstance(entry["include_bs"], bool):
            raise ValueError(f"{where}: 'include_bs' must be true or false.")  # noqa: TRY004 — see _read_session_json
        if entry["include_bs"] != plan.include_bs:
            raise ValueError(
                f"{where}: 'include_bs' is {entry['include_bs']} but plan_filings "
                f"gives {plan.include_bs}. The plan is route A's plan and is not "
                "edited by hand.",
            )
        result.append((plan, entry))
    return result


def _pdf_problems(where: str, plan: FilingPlan, entry: dict[str, Any]) -> list[str]:
    """Stop if the PDF is gone or is not the file the session read (rule 5)."""
    for key in ("pdf_sha256", "size_bytes"):
        if key not in entry:
            return [f"{where}: key '{key}' is absent."]
    recorded_sha = entry["pdf_sha256"]
    recorded_size = entry["size_bytes"]
    if not isinstance(recorded_sha, str) or not recorded_sha:
        return [f"{where}: 'pdf_sha256' must be a non-empty string."]
    if not _is_int(recorded_size):
        return [f"{where}: 'size_bytes' must be an integer."]
    try:
        (now,) = fingerprint_filings([(plan.fiscal_year, plan.pdf_path)])
    except FileNotFoundError:
        return [(
            f"{where}: the PDF {plan.pdf_path} is not on disk, so the figures "
            "cannot be tied to the filing they were read from."
        )]
    if now.sha256 != recorded_sha:
        return [(
            f"{where}: the PDF {plan.pdf_path} has changed since the session read "
            f"it. sha256 recorded {recorded_sha[:16]}…, now {now.sha256[:16]}…; "
            f"size recorded {recorded_size:,} bytes, now {now.size_bytes:,}. The "
            "figures belong to a file that is no longer there."
        )]
    return []


def _pages(where: str, entry: dict[str, Any], which: str) -> tuple[list[str], tuple[int, ...]]:
    """`pages_read.<which>`: present, a list of 1-based page numbers."""
    if "pages_read" not in entry:
        return [f"{where}: key 'pages_read' is absent."], ()
    pages_read = entry["pages_read"]
    if not isinstance(pages_read, dict):
        return [f"{where}: 'pages_read' must be a JSON object."], ()
    if which not in pages_read:
        return [f"{where}: key 'pages_read.{which}' is absent."], ()
    pages = pages_read[which]
    if not isinstance(pages, list) or not all(_is_int(p) and p >= 1 for p in pages):
        return [(
            f"{where}: 'pages_read.{which}' must be a list of 1-based page "
            f"numbers, got {pages!r}."
        )], ()
    return [], tuple(pages)


def _pass1_problems(where: str, plan: FilingPlan, pass1: object) -> list[str]:
    """Pass 1's shape, then what this filing's plan asks of it.

    The shape is `pass1_problems`, the same function route A's parser runs: every
    key the schema names is present, and every printed line has a non-empty
    `label`, a finite number `value` and a positive integer `page`. Each problem
    names the year, the field and the line index; this function adds the session
    file and the filing. An absent key is never read as zero (rule 3), and an empty
    list is the answer "the filing prints no such row". Then the plan: the years it
    asks for, each once, and the balance sheet exactly when it asks for one.
    """
    if pass1 is None:
        return [f"{where}: 'pass1' is null — Pass 1 has not been written."]
    if not isinstance(pass1, dict):
        return [f"{where}: 'pass1' must be a JSON object, not {type(pass1).__name__}."]

    problems = [f"{where}, {p}" for p in pass1_problems(pass1)]

    historical = pass1.get("historical_years")  # its shape is reported just above
    if isinstance(historical, list) and historical:
        years = [
            entry["year"] for entry in historical
            if isinstance(entry, dict) and "year" in entry and _is_int(entry["year"])
        ]
        duplicates = sorted({y for y in years if years.count(y) > 1})
        if duplicates:
            problems.append(
                f"{where}: pass1 gives year(s) {duplicates} more than once.",
            )
        if plan.target_years is not None and sorted(years) != sorted(plan.target_years):
            problems.append(
                f"{where}: the plan asks this filing for year(s) "
                f"{list(plan.target_years)}, and pass1 gives {sorted(years)}.",
            )

    balance = pass1.get("latest_balance_sheet")  # its shape is reported just above
    if isinstance(balance, dict):
        if not plan.include_bs and balance != {}:
            problems.append(
                f"{where}: the plan takes the balance sheet from another filing, so "
                "'pass1.latest_balance_sheet' must be {}.",
            )
        if plan.include_bs and not balance:
            problems.append(
                f"{where}: the plan takes the balance sheet from this filing, and "
                "'pass1.latest_balance_sheet' is empty.",
            )
    return problems


def _pass2_item_label(position: int, item: dict[str, Any]) -> str:
    """'pass2.non_recurring_items[i] (year Y, 'description')' — whichever are present.

    The index always names the item. The year and the description are added when the
    item carries them, because they are what a reader looks for in the filing. Both
    are read only after a presence test, and only into this label.
    """
    found: list[str] = []
    if "year" in item:
        found.append(f"year {item['year']}")
    if "description" in item:
        found.append(repr(item["description"]))
    suffix = f" ({', '.join(found)})" if found else ""
    return f"pass2.non_recurring_items[{position}]{suffix}"


def _pass2_shape_problems(where: str, pass2: dict[str, Any]) -> list[str]:
    """Pass 2's shape, checked as strictly as Pass 1's before route A's parser runs.

    Route A's parser (`_parse_nri_response`) is not changed: it is route A's too. It
    raises AttributeError on a `non_recurring_items` that is not a list, converts an
    `amount` of "12" to 12.0, accepts an `amount` of NaN, and names neither the item
    nor its year when one of six keys is absent. Each of those is checked here
    instead, so the stop names the filing and the item (rule 3).

    An absent `non_recurring_items` is left to the parser, whose message already
    explains why an absent list and an empty one are not the same answer.
    """
    if "non_recurring_items" not in pass2:
        return []
    items = pass2["non_recurring_items"]
    if not isinstance(items, list):
        return [(
            f"{where}: 'pass2.non_recurring_items' must be a list (an empty list "
            f"means none were found), got {type(items).__name__} {items!r}."
        )]
    problems: list[str] = []
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(
                f"{where}, pass2.non_recurring_items[{position}]: must be a JSON "
                f"object, got {type(item).__name__} {item!r}.",
            )
            continue
        label = _pass2_item_label(position, item)
        for key in _PASS2_ITEM_FIELDS:
            if key not in item:
                problems.append(f"{where}, {label}: key '{key}' is absent.")
        if "year" in item and not _is_int(item["year"]):
            problems.append(
                f"{where}, {label}: 'year' must be an integer, got {item['year']!r}.",
            )
        if "amount" in item and (not _is_number(item["amount"]) or item["amount"] <= 0):
            problems.append(
                f"{where}, {label}: 'amount' must be a finite JSON number above 0, got "
                f"{item['amount']!r}.",
            )
        if "page" in item and (not _is_int(item["page"]) or item["page"] < 1):
            problems.append(
                f"{where}, {label}: 'page' must be a positive integer (a 1-based PDF page), got {item['page']!r}.",
            )
        if "units" in item:
            if not isinstance(item["units"], dict):
                problems.append(
                    f"{where}, {label}: 'units' must be a JSON object, got {type(item['units']).__name__} {item['units']!r}.",
                )
            else:
                for ukey in ("printed", "page"):
                    if ukey not in item["units"]:
                        problems.append(f"{where}, {label}: key 'units.{ukey}' is absent.")
                if "printed" in item["units"] and (
                    not isinstance(item["units"]["printed"], str) or not item["units"]["printed"].strip()
                ):
                    problems.append(
                        f"{where}, {label}: 'units.printed' must be a non-empty string, got {item['units']['printed']!r}.",
                    )
                if "page" in item["units"] and (
                    not _is_int(item["units"]["page"]) or item["units"]["page"] < 1
                ):
                    problems.append(
                        f"{where}, {label}: 'units.page' must be a positive integer (a 1-based PDF page), got {item['units']['page']!r}.",
                    )
    return problems


def _pass2_problems(where: str, pass2: object) -> list[str]:
    """Pass 2 must be written, well-formed, and accepted by route A's parser."""
    if pass2 is None:
        return [f"{where}: 'pass2' is null — Pass 2 has not been written."]
    if not isinstance(pass2, dict):
        return [f"{where}: 'pass2' must be a JSON object, not {type(pass2).__name__}."]
    shape_problems = _pass2_shape_problems(where, pass2)
    if shape_problems:
        return shape_problems
    try:
        parse_pass2(json.dumps(pass2))
    except (ValueError, KeyError, TypeError) as exc:
        return [(f"{where}: pass2 was rejected by the Pass 2 parser: "
                 f"{type(exc).__name__}: {exc}")]
    return []


def _pass2_item_problems(where: str, plan: FilingPlan, pass2: object) -> list[str]:
    """Each Pass 2 non-recurring item's figure and unit words looked up on their
    cited pages; one problem per item not confirmed. A problem, not a failed check:
    the loader STOPS on it (P14b, backlog item 77).

    Run only when Pass 2's shape is usable and accepted by the parser, against the
    PDF proved by sha256.
    """
    if not isinstance(pass2, dict) or _pass2_shape_problems(where, pass2):
        return []
    try:
        parse_pass2(json.dumps(pass2))
    except (ValueError, KeyError, TypeError):
        return []
    try:
        failures = pass2_page_failures(
            json.dumps(pass2), Path(plan.pdf_path).read_bytes(),
        )
    except ValueError as exc:
        return [f"{where}: {exc}"]
    return [f"{where}: {failure}" for failure in failures]


def _unit_statement_problems(where: str, plan: FilingPlan, pass1: object) -> list[str]:
    """Each printed unit statement looked up on the page it cites; one problem per
    statement not found. A problem, not a failed check: the loader STOPS on it,
    because the scale read from it converts every figure, and a wrong scale moves
    every figure by 1,000 with nothing downstream to detect it (P14a).

    Run only when Pass 1's shape is usable (its own problems are reported by
    `_pass1_problems`), against the PDF `_pdf_problems` has proved is the one the
    session read. A PDF pdfplumber cannot open is a problem too.
    """
    if not isinstance(pass1, dict) or pass1_problems(pass1):
        return []
    try:
        failures = unit_statement_page_failures(
            json.dumps(pass1), Path(plan.pdf_path).read_bytes(),
        )
    except ValueError as exc:
        return [f"{where}: {exc}"]
    return [f"{where}: {failure}" for failure in failures]


def _filing_problems(
    path: Path, index: int, plan: FilingPlan, entry: dict[str, Any],
) -> list[str]:
    """Every reason this filing cannot be used, in reading order."""
    where = _filing_label(path, index, entry)
    problems = _pdf_problems(where, plan, entry)
    for key in ("pass1", "pass2"):
        if key not in entry:
            problems.append(f"{where}: key '{key}' is absent.")
    if problems:
        return problems
    problems += _pass1_problems(where, plan, entry["pass1"])
    problems += _unit_statement_problems(where, plan, entry["pass1"])
    problems += _pass2_problems(where, entry["pass2"])
    problems += _pass2_item_problems(where, plan, entry["pass2"])
    for which in ("pass1", "pass2"):
        page_problems, pages = _pages(where, entry, which)
        problems += page_problems
        if not page_problems and entry[which] is not None and not pages:
            problems.append(
                f"{where}: 'pages_read.{which}' is empty. Record the 1-based pages "
                f"read for {which}; they are how a reader finds each figure.",
            )
    return problems


def session_resolution(model: str, session_file: Path) -> ProviderResolution:
    """The label for figures read in a Claude Code session (rule 6).

    The provider is Claude, because the session is Claude. The transport names the
    session file. The credential says no API call was made, because none was.
    """
    return ProviderResolution(
        provider="claude",
        model=model,
        reasoning_label="as the Claude Code session ran; not set by this code",
        transport="claude-code-session",
        transport_label=(
            f"Claude Code session — figures read from the PDF in a Claude Code "
            f"session and stored in the session file {session_file}. The model ID "
            f"is as the session declared it; it cannot be verified"
        ),
        credential="claude-code-session",
        credential_source=(
            "none — no API call was made; the extraction was read from the "
            "session file on disk"
        ),
    )


def load_session_extraction(path: str | Path) -> SessionExtraction:
    """Check, parse and merge a session file exactly as route A would its answers.

    Raises:
        ValueError: naming the file, the filing index and its PDF, and the year
            and key where one applies, for every problem found. See the module
            docstring and docs/3-architecture/extraction.md for the stop list.
    """
    session_path = Path(path).resolve()
    data = _read_session_json(session_path)
    ticker, company_name = _read_identity(data, session_path)
    planned = _session_plans(data, session_path)

    # Every remaining problem is collected before stopping, so one `check` lists
    # them all. The model label is among them rather than ahead of them: a session
    # sets it last, and must still see its Pass 1 problems before it does.
    problems: list[str] = []
    try:
        _read_model(data, session_path)
    except ValueError as exc:
        problems.append(str(exc))
    for index, (plan, entry) in enumerate(planned):
        problems += _filing_problems(session_path, index, plan, entry)
    if problems:
        raise ValueError(
            f"{session_path}: the session file cannot be used. "
            f"{len(problems)} problem(s):\n" + "\n".join(f"  - {p}" for p in problems),
        )

    model = _read_model(data, session_path)  # proved present just above
    extractions: list[tuple[FilingPlan, FinancialStatements, list[NonRecurringItem]]] = []
    validation_errors: list[str] = []
    records: list[SessionFiling] = []
    for index, (plan, entry) in enumerate(planned):
        where = _filing_label(session_path, index, entry)
        financials, errors = parse_pass1(json.dumps(entry["pass1"]), ticker, company_name)
        # Each printed line looked up on its cited page, in the PDF `_pdf_problems`
        # has just proved is the one the session read (sha256). A line not found is
        # a failed check, shown with the arithmetic ones; an unreadable PDF stops,
        # naming the filing as every other loader stop does. `_filing_problems` has
        # proved the Pass 1 shape, so the only ValueError left here is the PDF's.
        try:
            errors += printed_line_page_failures(
                json.dumps(entry["pass1"]), Path(plan.pdf_path).read_bytes(),
            )
        except ValueError as exc:
            raise ValueError(f"{where}: {exc}") from exc
        items = parse_pass2(json.dumps(entry["pass2"]))
        # This filing to millions, once, after its Pass 2 and before the merge, as
        # route A does in extract_financials. `_filing_problems` has proved both
        # unit statements readable and found on their pages.
        units = filing_units(json.dumps(entry["pass1"]))
        financials, items = convert_filing_to_millions(financials, items, units)
        validation_errors += [f"{where}: {e}" for e in errors]
        extractions.append((plan, financials, items))
        _, pages1 = _pages(where, entry, "pass1")
        _, pages2 = _pages(where, entry, "pass2")
        records.append(SessionFiling(
            index=index,
            plan=plan,
            pdf_sha256=entry["pdf_sha256"],
            size_bytes=entry["size_bytes"],
            pages_pass1=pages1,
            pages_pass2=pages2,
            units=units,
        ))

    # Combined exactly as route A combines: one filing is returned as parsed,
    # several go through the one merge (extract_multi_year does the same).
    if len(extractions) == 1:
        _, merged, merged_items = extractions[0]
    else:
        merged, merged_items = merge_filing_extractions(extractions, ticker, company_name)

    return SessionExtraction(
        financials=merged,
        non_recurring=merged_items,
        resolution=session_resolution(model, session_path),
        validation_errors=validation_errors,
        session_file=str(session_path),
        filings=tuple(records),
    )


# ===========================================================================
# Subcommands
# ===========================================================================

def _select_filing(path: Path, index: int) -> tuple[FilingPlan, dict[str, Any], str]:
    """One filing's plan and entry, by its 0-based index."""
    data = _read_session_json(path)
    planned = _session_plans(data, path)
    if not 0 <= index < len(planned):
        raise ValueError(
            f"{path}: --filing {index} is out of range; the file has "
            f"{len(planned)} filing(s), indexed 0 to {len(planned) - 1}.",
        )
    plan, entry = planned[index]
    return plan, entry, _filing_label(path, index, entry)


def _open_verified_pdf(path: Path, index: int) -> tuple[FilingPlan, str]:
    """The filing's plan, after proving its PDF is the one the plan hashed."""
    plan, entry, where = _select_filing(path, index)
    problems = _pdf_problems(where, plan, entry)
    if problems:
        raise ValueError("\n".join(problems))
    return plan, where


def _page_texts(pdf_path: str, first: int, last: int) -> list[tuple[int, str | None]]:
    """(1-based page number, text layer or None) for pages first..last."""
    import pdfplumber

    texts: list[tuple[int, str | None]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number in range(first, last + 1):
            texts.append((number, pdf.pages[number - 1].extract_text()))
    return texts


def _page_count(pdf_path: str) -> int:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def cmd_plan(
    pdf_args: list[str], ticker: str, company_name: str, output: Path, force: bool,
) -> int:
    """Write a skeleton session file for these filings, planned as route A plans them."""
    if output.exists() and not force:
        raise ValueError(
            f"{output} already exists and is not overwritten. A filled session "
            "file is a session's work. Pass --force to replace it.",
        )
    ticker = ticker.upper()
    filings = parse_pdf_args(pdf_args, ticker)
    if len(filings) > 1:
        unyeared = [p for y, p in filings if y <= 0]
        if unyeared:
            raise ValueError(
                "With more than one filing each needs a fiscal year. No year for: "
                + ", ".join(unyeared) + ". Name them YEAR:PATH, or pass a folder.",
            )
    resolved: list[tuple[int, str | Path]] = [
        (year, str(Path(pdf).resolve())) for year, pdf in filings
    ]
    plans = plan_filings(resolved)
    prints = {
        fp.path: fp
        for fp in fingerprint_filings([(p.fiscal_year, p.pdf_path) for p in plans])
    }

    skeleton = {
        "format": SESSION_FORMAT,
        "ticker": ticker,
        "company_name": company_name,
        "extracted_by": {"model": None, "tool": "Claude Code", "date": None},
        "filings": [
            {
                "fiscal_year": plan.fiscal_year,
                "pdf_path": plan.pdf_path,
                "pdf_sha256": prints[plan.pdf_path].sha256,
                "size_bytes": prints[plan.pdf_path].size_bytes,
                "target_years": (
                    None if plan.target_years is None else list(plan.target_years)
                ),
                "include_bs": plan.include_bs,
                "pages_read": {"pass1": [], "pass2": []},
                "pass1": None,
                "pass2": None,
            }
            for plan in plans
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(skeleton, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")

    print(f"Wrote {output} — {len(plans)} filing(s) for {ticker}:")
    for index, plan in enumerate(plans):
        years = ("every year it presents" if plan.target_years is None
                 else f"year(s) {list(plan.target_years)} only")
        bs = " + balance sheet" if plan.include_bs else ""
        print(f"  [{index}] fiscal {plan.fiscal_year}  {Path(plan.pdf_path).name}  "
              f"sha256 {prints[plan.pdf_path].sha256[:16]}…  -> {years}{bs}")
    print("The fiscal year comes from the filename. Check each one against the "
          "filing's cover page before extracting.")
    return 0


def _matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def cmd_locate(path: Path, index: int) -> int:
    """Print the pages where statement titles and non-recurring keywords appear.

    Page numbers and match counts only. Never a figure (rule 1).
    """
    plan, where = _open_verified_pdf(path, index)
    total = _page_count(plan.pdf_path)
    pages = _page_texts(plan.pdf_path, 1, total)
    no_text = [number for number, text in pages if not text]

    print(f"{where}: {total} page(s). Page numbers are 1-based PDF pages, as the "
          "Read tool and `text --pages` count them.")
    if no_text:
        print(f"  {len(no_text)} page(s) have no text layer and cannot be searched: "
              f"{_compress(no_text)}")

    print("\nStatement titles (title line = a line holding the title, no digit, "
          f"at most {_TITLE_LINE_MAX_CHARS} characters):")
    for label, pattern in _STATEMENT_PATTERNS:
        headings: list[int] = []
        mentions: list[str] = []
        for number, text in pages:
            if not text:
                continue
            count = _matches(text, pattern)
            if not count:
                continue
            mentions.append(f"{number} ({count})")
            if any(
                _matches(line, pattern)
                and len(line.strip()) <= _TITLE_LINE_MAX_CHARS
                and not re.search(r"\d", line)
                for line in text.splitlines()
            ):
                headings.append(number)
        print(f"  {label}")
        print(f"    title line on pages: {_compress(headings) if headings else 'none found'}")
        print(f"    mentioned on pages (count): "
              f"{', '.join(mentions) if mentions else 'none found'}")

    print("\nNon-recurring keywords (page (count)):")
    for label, pattern in _NRI_PATTERNS:
        mentions = []
        for number, text in pages:
            if not text:
                continue
            count = _matches(text, pattern)
            if count:
                mentions.append(f"{number} ({count})")
        print(f"  {label}: {', '.join(mentions) if mentions else 'none found'}")
    return 0


def _compress(numbers: list[int]) -> str:
    """[1, 2, 3, 7] -> '1-3, 7'. An empty list prints as 'none'."""
    if not numbers:
        return "none"
    runs: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        runs.append(f"{start}-{previous}" if start != previous else f"{start}")
        start = previous = number
    runs.append(f"{start}-{previous}" if start != previous else f"{start}")
    return ", ".join(runs)


def _parse_page_range(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", text)
    if not match:
        raise ValueError(f"--pages must be A-B or A, 1-based; got {text!r}.")
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) is not None else first
    return first, last


def cmd_text(path: Path, index: int, page_range: str) -> int:
    """Print the text layer of pages A..B of the filing's PDF. Computes nothing."""
    first, last = _parse_page_range(page_range)
    plan, where = _open_verified_pdf(path, index)
    total = _page_count(plan.pdf_path)
    if first < 1 or last < first or last > total:
        raise ValueError(
            f"{where}: --pages {first}-{last} is not a range within pages 1 to {total}.",
        )
    if last - first + 1 > MAX_TEXT_PAGES:
        raise ValueError(
            f"--pages {first}-{last} is {last - first + 1} pages; at most "
            f"{MAX_TEXT_PAGES} are printed per call. Use `locate` to find the "
            "pages you need.",
        )
    for number, text in _page_texts(plan.pdf_path, first, last):
        print(f"=== page {number} ===")
        print(text if text else "(this page has no text layer)")
    return 0


def cmd_prompt(path: Path, index: int, which_pass: int) -> int:
    """Print the system and user prompt route A sends for this filing's pass."""
    plan, entry, where = _select_filing(path, index)
    if which_pass == 1:
        system_prompt, user_prompt = pass1_prompts(plan)
    else:
        if "pass1" not in entry:
            raise ValueError(f"{where}: key 'pass1' is absent.")
        problems = _pass1_problems(where, plan, entry["pass1"])
        if problems:
            raise ValueError(
                "Pass 2's prompt carries a summary built from this filing's Pass 1, "
                "so Pass 1 must be complete first:\n"
                + "\n".join(f"  - {p}" for p in problems),
            )
        ticker, company_name = _read_identity(_read_session_json(path), path)
        # parse_pass1 prints its arithmetic table. Send it to stderr, so stdout
        # holds the prompt and nothing else.
        with contextlib.redirect_stdout(sys.stderr):
            financials, _ = parse_pass1(json.dumps(entry["pass1"]), ticker, company_name)
        system_prompt, user_prompt = pass2_prompts(plan, financials)

    print(f"=== SYSTEM PROMPT — Pass {which_pass}, {where} ===")
    print(system_prompt)
    print(f"\n=== USER PROMPT — Pass {which_pass}, {where} ===")
    print(user_prompt)
    print("\nIn route A the PDF is attached to this prompt. In a session, read it "
          "with `locate` and `text`, and write the JSON object into "
          f"filings[{index}].pass{which_pass}.")
    return 0


def cmd_check(path: Path) -> int:
    """Run the loader. Exit 0 clean, 1 failed checks only, 2 the loader stops."""
    session_path = path.resolve()
    try:
        session = load_session_extraction(session_path)
    except ValueError as exc:
        print(f"STOPPED — {exc}")
        _print_pass1_tables(session_path)
        return 2

    print(f"\n{describe_resolution(session.resolution)}")
    for record in session.filings:
        print(f"  filings[{record.index}] {Path(record.plan.pdf_path).name}  "
              f"sha256 {record.pdf_sha256[:16]}…  "
              f"pages read: pass 1 {_compress(list(record.pages_pass1))}; "
              f"pass 2 {_compress(list(record.pages_pass2))}")
        print(f"    units {record.units.money.printed!r} (page "
              f"{record.units.money.page}) -> money in {record.units.money.scale.word}; "
              f"share_units {record.units.shares.printed!r} (page "
              f"{record.units.shares.page}) -> share count in "
              f"{record.units.shares.scale.word}. Converted to millions.")
    # `years` covers every year ANY of the three statements reaches, since
    # `P3d-invisible-year`; the balance sheet years beside it are listed in
    # full. This is the summary of what the session file holds, so a year with
    # a cash flow statement and no income statement belongs in it — before
    # that unit it was in no line of this command's output (backlog item 116).
    print(f"  Years: {session.financials.years}  |  "
          f"balance sheet(s): {[b.year for b in session.financials.balance_sheets]}  |  "
          f"non-recurring items: {len(session.non_recurring)}")
    if session.validation_errors:
        print(f"\n{len(session.validation_errors)} failed check(s). Route A keeps "
              "these figures and shows the failure after its last retry. Read the "
              "rows again; correct a line only where it does not match the row "
              "printed in the filing, never to make a check pass:")
        for error in session.validation_errors:
            print(f"  - {error}")
        return 1
    print("\nClean: every key present, every line well formed, every PDF unchanged, "
          "both unit statements found on their pages, every printed subtotal and "
          "total agrees with Python's sum of the lines, and every printed line was "
          "found on the page it cites.")
    return 0


def _print_pass1_tables(path: Path) -> None:
    """After a stop, print the arithmetic table of every filing whose Pass 1 is whole.

    So a session that has written Pass 1 and not yet Pass 2 sees its Pass 1
    arithmetic now, rather than after Pass 2.
    """
    try:
        data = _read_session_json(path)
        ticker, company_name = _read_identity(data, path)
        planned = _session_plans(data, path)
    except ValueError:
        return
    for index, (plan, entry) in enumerate(planned):
        where = _filing_label(path, index, entry)
        if "pass1" not in entry or _pass1_problems(where, plan, entry["pass1"]):
            continue
        print(f"\nPass 1 arithmetic for {where}:")
        _, errors = parse_pass1(json.dumps(entry["pass1"]), ticker, company_name)
        for error in errors:
            print(f"  - {error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.session_extraction",
        description="Route B: extract 10-K figures in a Claude Code session file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="write a skeleton session file")
    p.add_argument("pdfs", nargs="+",
                   help="a folder of 10-K PDFs, PDF path(s), or YEAR:PATH entries")
    p.add_argument("-t", "--ticker", required=True)
    p.add_argument("-n", "--company-name", default="",
                   help="company name; empty lets Pass 1's answer supply it, as in route A")
    p.add_argument("-o", "--output", required=True, type=Path)
    p.add_argument("--force", action="store_true", help="overwrite an existing file")

    p = sub.add_parser("locate", help="pages holding statement titles and NRI keywords")
    p.add_argument("file", type=Path)
    p.add_argument("--filing", type=int, required=True, help="0-based filing index")

    p = sub.add_parser("text", help="print the text layer of a page range")
    p.add_argument("file", type=Path)
    p.add_argument("--filing", type=int, required=True, help="0-based filing index")
    p.add_argument("--pages", required=True, help="1-based A-B, at most 20 pages")

    p = sub.add_parser("prompt", help="print the prompt route A sends")
    p.add_argument("file", type=Path)
    p.add_argument("--filing", type=int, required=True, help="0-based filing index")
    p.add_argument("--pass", dest="which_pass", type=int, choices=[1, 2], required=True)

    p = sub.add_parser("check", help="run the loader and report every problem")
    p.add_argument("file", type=Path)
    return parser


# The error handler this module puts on its own output streams.
#
# `prompt --pass 2` prints the Pass 2 prompt, and that prompt holds two U+2192
# RIGHTWARDS ARROW (`claude_extractor.py:412-413`). A redirected stdout on this
# Windows machine encodes in cp1252, which has no such character, so the write raised
# `UnicodeEncodeError` and the command stopped after 19 of its 82 lines (backlog item
# 113). **The prompt is the text route A sends to the model, so no byte of it may
# change** (`docs/2-rules/llm-boundary.md`, and AGENTS.md makes a change to the
# boundary an escalation). The stream changes instead.
#
# `namereplace` writes every character the console's encoding holds exactly as it is,
# so a UTF-8 console still prints U+2192 as the arrow itself; any other character is
# written as its Unicode name, `\N{RIGHTWARDS ARROW}`. That is why it is this handler
# and not `replace`, which prints `?`, or `ignore`, which prints nothing: both lose
# the fact that a character was there, and a reader cannot tell a dropped arrow from a
# prompt that never had one.
#
# This comment is written in ASCII on purpose. A file about a console that cannot hold
# a character should not need that console to hold one to be read.
UNENCODABLE_CHARACTER_HANDLER = "namereplace"


def name_unencodable_characters(stream: object) -> bool:
    """Make `stream` write a character its encoding cannot hold as its Unicode name.

    A stream that encodes text to bytes — `sys.stdout` and `sys.stderr`, on a console
    or down a pipe — is an `io.TextIOWrapper`. Its error handler is reconfigured in
    place, and its encoding is left alone: this changes nothing about a character the
    console can already hold.

    Any other object performs no encode step at all (an `io.StringIO` a caller put in
    `sys.stdout`'s place keeps `str`), so no character can be lost in it and there is
    nothing to set. Returns True when the handler was set and False when the stream
    does not encode, so a caller can tell the two apart.
    """
    if not isinstance(stream, io.TextIOWrapper):
        return False
    stream.reconfigure(errors=UNENCODABLE_CHARACTER_HANDLER)
    return True


@contextlib.contextmanager
def naming_unencodable_characters(stream: object) -> Iterator[bool]:
    """Name unencodable characters on `stream` for the body, then put back its handler.

    `sys.stdout` and `sys.stderr` belong to whoever called this module, not to this
    module. `main()` used to set `namereplace` on both and never put the old handler
    back, so an in-process caller kept the changed handler for the life of its
    process — backlog item 124. `_pytest.capture.CaptureIO` is an `io.TextIOWrapper`
    subclass, so under pytest that reached every test that ran afterwards, and the
    `P14f` tester paid for it with three subprocesses.

    The handler is read before it is set and written back in a `finally`, so the
    stream leaves this block exactly as it arrived. Every character is encoded at the
    moment it is written (`io.TextIOWrapper.write` encodes into the binary buffer), so
    text written inside the block is already bytes before the handler goes back: the
    restore cannot un-name a character that was already named.

    Yields what `name_unencodable_characters` returned, so a caller can tell a stream
    that encodes from one that does not.
    """
    if not isinstance(stream, io.TextIOWrapper):
        # No encode step happens here, so nothing was set and there is nothing to
        # put back. `name_unencodable_characters` states that case and its reason.
        yield name_unencodable_characters(stream)
        return
    previous = stream.errors
    if not isinstance(previous, str):
        # Rule 3. `reconfigure(errors=None)` means "leave the handler alone", so a
        # handler that does not read as a name would silently leave `namereplace`
        # behind — the defect this function exists to close, wearing a quieter face.
        # `TypeError` rather than `ValueError` because the complaint is about the
        # type of `stream.errors`, and because `main`'s `except (ValueError,
        # FileNotFoundError)` must not turn this into an ordinary "ERROR: …" exit.
        raise TypeError(
            "cannot name unencodable characters on this stream: its error handler "
            f"reads as {previous!r}, which is not a handler name, so the handler "
            f"this would set could not be put back afterwards. Stream: "
            f"{type(stream).__name__} {stream!r}")
    was_set = name_unencodable_characters(stream)
    try:
        yield was_set
    finally:
        stream.reconfigure(errors=previous)


def main(argv: list[str] | None = None) -> int:
    # Every subcommand prints through these two streams, so wrapping the whole body
    # once covers `plan`, `locate`, `text`, `prompt` and `check`, and argparse's own
    # usage message with them. stderr is included because `cmd_prompt` sends
    # `parse_pass1`'s arithmetic table there. Both handlers go back on the way out:
    # `main` is a function an importer may call, and it does not own these streams.
    with naming_unencodable_characters(sys.stdout), \
            naming_unencodable_characters(sys.stderr):
        args = _build_parser().parse_args(argv)
        try:
            if args.command == "plan":
                return cmd_plan(args.pdfs, args.ticker, args.company_name,
                                args.output, args.force)
            if args.command == "locate":
                return cmd_locate(args.file.resolve(), args.filing)
            if args.command == "text":
                return cmd_text(args.file.resolve(), args.filing, args.pages)
            if args.command == "prompt":
                return cmd_prompt(args.file.resolve(), args.filing, args.which_pass)
            return cmd_check(args.file)
        except (ValueError, FileNotFoundError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
