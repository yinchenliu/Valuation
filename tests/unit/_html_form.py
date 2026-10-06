"""Parse a rendered HTML form into the body a browser would submit.

**Why this exists.** `P3c-one-number` moved every derived ratio out of the
form's `value` attribute and into its `placeholder`, because a browser submits
the first and never the second. A test that hand-writes a POST body cannot see
that difference: it posts whatever the test author typed, so it would stay green
if the `value` attribute came back tomorrow. The only test that can see it is one
that reads the rendered page and submits **what the browser would send**.

This module holds no expected value. It encodes one contract, and the contract is
not this repository's — it is the HTML form-submission algorithm (WHATWG HTML,
"constructing the entry list"):

  * a control with no `name` is not submitted;
  * a `disabled` control is not submitted;
  * an `<input>` with no `value` attribute submits the empty string;
  * a `placeholder` is never submitted, whatever it holds;
  * a checkbox or radio is submitted **only when it is `checked`**, and then with
    its `value`, or `"on"` when it has none;
  * `type="submit"`, `type="button"`, `type="reset"`, `type="image"` and
    `type="file"` are not submitted by this parser (no button is "clicked" and no
    file is chosen);
  * a `<select>` submits its `selected` `<option>`, or its first option when none
    carries `selected`; an option with no `value` attribute submits its text.

Nothing here reads `templates/`, and nothing here imports the application.
"""

from __future__ import annotations

import html
import re

__all__ = ["form_tag", "parse_form", "placeholders"]

# Controls a browser does not include in a normal submission.
_NOT_SUBMITTED_TYPES = frozenset({"submit", "button", "reset", "image", "file"})


def _attrs(tag: str) -> dict[str, str]:
    """Every `name="value"` and every bare attribute of one start tag."""
    found: dict[str, str] = {}
    for match in re.finditer(r'([A-Za-z_:][-A-Za-z0-9_:.]*)(?:\s*=\s*"([^"]*)")?', tag[1:]):
        key = match.group(1).lower()
        if key in found:
            continue
        found[key] = html.unescape(match.group(2)) if match.group(2) is not None else ""
    return found


def form_tag(body: str, action: str) -> str:
    """The whole `<form action="{action}" ...> ... </form>` element.

    Raises AssertionError naming `action` when the page carries no such form, so
    a page that failed to render cannot be read as a form that submits nothing.
    """
    start = re.search(rf'<form[^>]*\saction="{re.escape(action)}"[^>]*>', body)
    assert start is not None, f'no <form action="{action}"> on the page'
    end = body.index("</form>", start.start())
    return body[start.start() : end + len("</form>")]


def parse_form(body: str, action: str) -> dict[str, str]:
    """What a browser would POST from the form at `action`, nothing touched.

    Returns one entry per submitted control, in document order. A field the page
    renders empty is present with the value `""` — which is the whole point: an
    absent key and an empty key are different POST bodies, and only one of them
    is what an untouched browser form sends.
    """
    form = form_tag(body, action)
    submitted: dict[str, str] = {}

    for tag in re.findall(r"<input[^>]*>", form):
        attrs = _attrs(tag)
        name = attrs.get("name")
        if not name or "disabled" in attrs:
            continue
        kind = attrs.get("type", "text").lower()
        if kind in _NOT_SUBMITTED_TYPES:
            continue
        if kind in ("checkbox", "radio"):
            if "checked" not in attrs:
                continue
            submitted[name] = attrs.get("value", "on")
            continue
        # Everything else — text, number, hidden, email, … — submits its `value`
        # attribute, and the EMPTY STRING when it has none. `placeholder` is not
        # read here, and that omission is the behaviour under test.
        submitted[name] = attrs.get("value", "")

    for select in re.finditer(r"<select([^>]*)>(.*?)</select>", form, re.DOTALL):
        attrs = _attrs("<select" + select.group(1) + ">")
        name = attrs.get("name")
        if not name or "disabled" in attrs:
            continue
        options = re.findall(r"<option([^>]*)>(.*?)</option>", select.group(2), re.DOTALL)
        if not options:
            continue
        chosen = next(
            (opt for opt in options if "selected" in _attrs("<option" + opt[0] + ">")),
            options[0],
        )
        opt_attrs = _attrs("<option" + chosen[0] + ">")
        submitted[name] = opt_attrs.get("value", html.unescape(chosen[1]).strip())

    for area in re.finditer(r"<textarea([^>]*)>(.*?)</textarea>", form, re.DOTALL):
        attrs = _attrs("<textarea" + area.group(1) + ">")
        name = attrs.get("name")
        if name and "disabled" not in attrs:
            submitted[name] = html.unescape(area.group(2))

    return submitted


def placeholders(body: str, action: str) -> dict[str, str]:
    """The `placeholder` of every named `<input>` in the form at `action`.

    A browser never submits one. `parse_form` above therefore ignores them, and
    this function exists so a test can assert that the figure a reader SEES is
    the one that is NOT posted.
    """
    found: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", form_tag(body, action)):
        attrs = _attrs(tag)
        name = attrs.get("name")
        if name and "placeholder" in attrs:
            found[name] = attrs["placeholder"]
    return found
