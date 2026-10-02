"""The web routes for a session file, and the extraction label recorded as it ran.

`P9b-session-web` (accepted at `be1c077`) added `POST /upload-session`, a
`session_file` parameter on `GET /assumptions` and `POST /valuation`, one
`_run_extraction` for both routes, and a `ProviderResolution` recorded in the cache
entry when the extraction runs. Its programmer and its reviewer proved each of
those with scratch scripts under `/tmp/`. This file holds the proofs.

The eight groups of `.agent/assignments/P9b-route-tests.md`, in order. Group 8
(backlog item 52) is a red test and lives in `test_routes_session_rule3_red.py`;
its cache-MISS half, which already stops, is here.

**Where every expected value comes from.** Nothing here was read off a page the
code rendered. Each expected value is one of:

  * a figure or string written by hand into the session file in
    `_session_route_helpers.py` (ticker `TST`, company `Test Co`, the model ID,
    revenue 1,000 and 2,000, the excluded item's description);
  * a contract stated outside the code path under test: the route's declared
    signature (`File(...)`, `Form(...)`, `status_code=303`), the P9b assignment's
    steps, the P9a assignment's step 11 for the session label
    (`provider="claude"`, the declared model, a transport label saying "Claude Code
    session" and naming the file, a credential source saying no API call was made),
    and `docs/8-build/environment.md` section 3 for route A on this machine
    ("the public API with ANTHROPIC_API_KEY");
  * the field names a stop must name, which are the parameter names the routes
    declare.

The comment above each assertion says which.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from api import routes_valuation
from ingestion.claude_extractor import resolve_provider
from tests.unit._session_route_helpers import (
    COMPANY,
    EXCLUDED_ITEM_DESCRIPTION,
    FISCAL_YEAR,
    MODEL,
    REVENUE_SHOWN,
    TICKER,
    VALUATION_FORM,
    error_text,
    hidden_value,
    install_loader_spy,
    install_price_stub,
    install_route_a_stub,
    label_rows,
    make_pdf,
    open_closed_client,
    revenue_row,
    session_dict,
    text_of,
    write_session,
)


@pytest.fixture
def closed_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """Every boundary closed, no credential, uploads under tmp_path. See the helper."""
    return open_closed_client(monkeypatch, tmp_path)


@pytest.fixture
def price_calls(closed_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list:
    """`fetch_price_data` answering only ("TST", 5, "monthly"). See the helper.

    Depends on `closed_client` so it is installed AFTER the closed boundary,
    whatever order a test lists its fixtures in.
    """
    return install_price_stub(monkeypatch)


@pytest.fixture
def loader_calls(monkeypatch: pytest.MonkeyPatch) -> list:
    """A counting spy around the real `load_session_extraction`. See the helper."""
    return install_loader_spy(monkeypatch)


@pytest.fixture
def session_path(tmp_path: Path) -> Path:
    """A well-formed session file on disk, and the PDF it names."""
    pdf = make_pdf(tmp_path)
    return write_session(tmp_path, session_dict(pdf))


def _assert_session_label(body: str, session_file: Path) -> None:
    """The four label rows a session extraction must show.

    Expected values: P9a assignment step 11 (`.agent/assignments/P9a-session-route.md:198-201`):
    provider "claude" (the template upper-cases it), the model the session DECLARED
    (MODEL, written into the file by hand), a transport label that says the figures
    were read in a Claude Code session and names the session file, and a credential
    source that says no API call was made.
    """
    rows = label_rows(body)
    assert rows is not None, "no extraction label on the page"
    assert rows["Provider"] == "CLAUDE"
    assert rows["Model"] == MODEL
    assert "Claude Code session" in rows["Transport"]
    assert str(session_file) in rows["Transport"]
    assert "no API call was made" in rows["Credential source"]


# ===========================================================================
# 1. GET / shows both forms; the second posts to /upload-session
# ===========================================================================


def test_front_page_offers_both_routes_and_the_second_form_posts_a_session_file(
    closed_client: TestClient,
) -> None:
    """Expected values: P9b assignment step 1 (a second form, posting to
    `/upload-session`, one file input, no JavaScript) and the route's declared
    signature `session_file: UploadFile = File(...)` (`api/routes_upload.py:108`),
    which only a multipart body carrying a file field of that name can satisfy.
    """
    response = closed_client.get("/")
    assert response.status_code == 200
    body = response.text

    forms = re.findall(r"<form[^>]*>.*?</form>", body, re.DOTALL)
    # Two routes, two forms (step 1).
    assert len(forms) == 2
    assert 'action="/upload"' in forms[0]

    second = forms[1]
    opening = re.match(r"<form[^>]*>", second)
    assert opening is not None
    assert 'action="/upload-session"' in opening.group(0)
    assert 'method="post"' in opening.group(0)
    assert 'enctype="multipart/form-data"' in opening.group(0)
    file_input = re.search(r'<input[^>]*name="session_file"[^>]*>', second)
    assert file_input is not None, "the second form has no session_file input"
    assert 'type="file"' in file_input.group(0)
    # "Add no JavaScript" (step 1).
    assert "<script" not in body


def test_the_session_form_is_accepted_by_the_route_it_targets(
    closed_client: TestClient, session_path: Path,
) -> None:
    """Submit the second form's own field name to its own action.

    Expected value: 303, not 422. FastAPI answers 422 when a declared `File(...)`
    parameter is absent, so a form whose input name the route does not declare
    fails here. 303 is the route's declared `status_code`.
    """
    body = closed_client.get("/").text
    second = re.findall(r"<form[^>]*>.*?</form>", body, re.DOTALL)[1]
    action = re.search(r'action="([^"]+)"', second).group(1)  # type: ignore[union-attr]
    name = re.search(r'<input[^>]*type="file"[^>]*name="([^"]+)"', second)
    name = name or re.search(r'<input[^>]*name="([^"]+)"[^>]*type="file"', second)
    assert name is not None

    response = closed_client.post(
        action,
        files={name.group(1): ("session.json", session_path.read_bytes())},
        follow_redirects=False,
    )
    assert response.status_code == 303


# ===========================================================================
# 2. POST /upload-session saves under uploads/session/ and answers 303
# ===========================================================================


def test_upload_session_saves_the_file_and_redirects_naming_it(
    closed_client: TestClient, tmp_path: Path, session_path: Path,
) -> None:
    """Expected values:

    * 303 — `status_code=303` declared at `api/routes_upload.py:119`.
    * the location is `/assumptions` with `session_file=<saved path>` — P9b step 2.
    * the file lands at `UPLOAD_DIR/session/<name>` — P9b step 2 ("under
      `uploads/session/`"), with `UPLOAD_DIR` pointed at `tmp_path/uploads` by the
      fixture.
    * the bytes on disk are the bytes uploaded.
    """
    uploaded = session_path.read_bytes()
    response = closed_client.post(
        "/upload-session",
        files={"session_file": ("tst_session.json", uploaded)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert location.path == "/assumptions"
    saved = tmp_path / "uploads" / "session" / "tst_session.json"
    assert parse_qs(location.query) == {"session_file": [str(saved)]}
    assert saved.read_bytes() == uploaded


def test_upload_then_follow_the_redirect_reaches_the_assumptions_page_with_the_label(
    closed_client: TestClient, tmp_path: Path, session_path: Path,
) -> None:
    """The whole web path a user takes: upload, follow the 303, read the page.

    Expected values: the session label (P9a step 11, see `_assert_session_label`)
    naming the SAVED file, and the revenue row 1,000 / 2,000 written by hand into
    the file (`_session_route_helpers.REVENUE_SHOWN`).
    """
    response = closed_client.post(
        "/upload-session",
        files={"session_file": ("tst_session.json", session_path.read_bytes())},
    )
    assert response.status_code == 200
    assert error_text(response.text) is None
    saved = (tmp_path / "uploads" / "session" / "tst_session.json").resolve()
    _assert_session_label(response.text, saved)
    assert revenue_row(response.text) == REVENUE_SHOWN


@pytest.mark.parametrize("bad_name", [".", ".."])
def test_upload_session_with_no_usable_filename_answers_400_naming_the_field(
    closed_client: TestClient, tmp_path: Path, bad_name: str,
) -> None:
    """Rule 3: a missing filename stops and names the field.

    Expected values: 400 and a body naming `session_file` — the assignment's item 2.
    `.` and `..` are names with no usable final component (`Path(".").name == ""`,
    `".."` is the parent). Nothing may be written.
    """
    response = closed_client.post(
        "/upload-session",
        files={"session_file": (bad_name, b"{}")},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert response.json()["detail"].startswith("session_file:")
    session_dir = tmp_path / "uploads" / "session"
    assert not session_dir.exists() or list(session_dir.iterdir()) == []


def test_upload_session_with_no_file_field_answers_422_naming_the_field(
    closed_client: TestClient,
) -> None:
    """Expected: 422 with `session_file` in the error location — FastAPI's answer to
    an absent `File(...)` parameter, the route's declared signature."""
    response = closed_client.post("/upload-session", data={}, follow_redirects=False)
    assert response.status_code == 422
    locations = [err["loc"] for err in response.json()["detail"]]
    assert ["body", "session_file"] in locations


def test_upload_session_keeps_only_the_final_path_component(
    closed_client: TestClient, tmp_path: Path,
) -> None:
    """A crafted name cannot write outside `uploads/session/`.

    Expected value: `_save_session_upload`'s docstring (`api/routes_upload.py:42-43`):
    "Only the final path component of the name is kept, so a crafted name such as
    '../x.json' cannot write outside the directory." The final component of
    `../../escape.json` is `escape.json`.
    """
    response = closed_client.post(
        "/upload-session",
        files={"session_file": ("../../escape.json", b"{}")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (tmp_path / "uploads" / "session" / "escape.json").read_bytes() == b"{}"
    assert not (tmp_path / "escape.json").exists()
    assert not (tmp_path / "uploads" / "escape.json").exists()


# ===========================================================================
# 3. GET /assumptions?session_file=… : 200, the label, the ticker from the file
# ===========================================================================


def test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity(
    closed_client: TestClient, session_path: Path,
) -> None:
    """No ticker in the request; the page takes it from the file.

    Expected values: ticker `TST` and company `Test Co` written into the file
    (P9b step 5: "the ticker shown and forwarded comes from the loaded file"); the
    session path forwarded as a hidden field (step 7); the label (P9a step 11);
    revenue 1,000 / 2,000 from the file. No credential is set in this process
    (`closed_client`), and route B needs none.
    """
    response = closed_client.get("/assumptions", params={"session_file": str(session_path)})

    assert response.status_code == 200
    assert error_text(response.text) is None
    _assert_session_label(response.text, session_path)
    assert hidden_value(response.text, "ticker") == TICKER
    assert hidden_value(response.text, "company_name") == COMPANY
    assert hidden_value(response.text, "session_file") == str(session_path)
    assert hidden_value(response.text, "files") == ""
    assert revenue_row(response.text) == REVENUE_SHOWN


def test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both(
    closed_client: TestClient, session_path: Path,
) -> None:
    """Expected: the page's error names the request's ticker `OTHER` and the file's
    `TST` (assignment item 3: "the page names both"). Nothing is cached: a stopped
    page must not leave an entry for `POST /valuation` to pick up."""
    response = closed_client.get(
        "/assumptions", params={"session_file": str(session_path), "ticker": "OTHER"},
    )

    assert response.status_code == 200
    message = error_text(response.text)
    assert message is not None
    assert "'OTHER'" in message
    assert "'TST'" in message
    assert routes_valuation._extraction_cache == {}


def test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both(
    closed_client: TestClient, session_path: Path,
) -> None:
    """Expected: the error names `Other Corp` (request) and `Test Co` (file)."""
    response = closed_client.get(
        "/assumptions",
        params={"session_file": str(session_path), "company_name": "Other Corp"},
    )

    message = error_text(response.text)
    assert message is not None
    assert "'Other Corp'" in message
    assert "'Test Co'" in message


def test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing(
    closed_client: TestClient, session_path: Path,
) -> None:
    """The ticker reaches the price fetch, so a mismatch must stop first.

    `fetch_price_data` is closed (raises); the expected error names both tickers,
    which it could not if the price fetch had been reached first.
    """
    form = VALUATION_FORM | {"ticker": "OTHER", "session_file": str(session_path)}
    response = closed_client.post("/valuation", data=form)

    message = error_text(response.text)
    assert message is not None
    assert "'OTHER'" in message
    assert "'TST'" in message


# ===========================================================================
# 4. POST /valuation with session_file: the session label, hit and miss
# ===========================================================================


def test_valuation_on_a_cache_hit_shows_the_session_label(
    closed_client: TestClient, session_path: Path, price_calls: list, loader_calls: list,
) -> None:
    """GET /assumptions caches the extraction; POST /valuation reads it back.

    Expected values: one loader call in total (the GET's), so the POST took the
    cache-hit branch; the session label (P9a step 11); the price fetched for the
    file's ticker only; the excluded item, written into the file with confidence
    `low`, listed as excluded (`partition_by_confidence` docstring); "public API"
    absent, because nothing on this path used it.
    """
    assumptions = closed_client.get("/assumptions", params={"session_file": str(session_path)})
    assert error_text(assumptions.text) is None
    assert len(loader_calls) == 1

    response = closed_client.post(
        "/valuation", data=VALUATION_FORM | {"session_file": str(session_path)},
    )

    assert response.status_code == 200
    assert error_text(response.text) is None, error_text(response.text)
    assert len(loader_calls) == 1  # no second load: the cache answered
    _assert_session_label(response.text, session_path)
    assert price_calls == [(TICKER, 5, "monthly")]
    assert "public API" not in text_of(response.text)
    assert EXCLUDED_ITEM_DESCRIPTION in text_of(response.text)


def test_valuation_on_a_cache_miss_shows_the_session_label(
    closed_client: TestClient, session_path: Path, price_calls: list, loader_calls: list,
) -> None:
    """Straight to POST /valuation, empty cache: the route loads the file itself.

    Expected values: exactly one loader call, for this file; then as above.
    """
    response = closed_client.post(
        "/valuation", data=VALUATION_FORM | {"session_file": str(session_path)},
    )

    assert response.status_code == 200
    assert error_text(response.text) is None, error_text(response.text)
    assert loader_calls == [str(session_path)]
    _assert_session_label(response.text, session_path)
    assert price_calls == [(TICKER, 5, "monthly")]
    assert "public API" not in text_of(response.text)


# ===========================================================================
# 5. The label is recorded, not re-derived
# ===========================================================================


def _route_a_files(pdf: Path) -> str:
    # The `year:path` shape `_parse_files_param` reads (`api/routes_valuation.py:94-103`).
    return f"{FISCAL_YEAR}:{pdf}"


def test_route_a_label_survives_removing_the_key_on_a_cache_hit(
    closed_client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    price_calls: list,
) -> None:
    """Extract with a key set; remove it; value from the cache.

    Expected values:
      * route A with only ANTHROPIC_API_KEY set is "the public API with
        ANTHROPIC_API_KEY" (`docs/8-build/environment.md:95`, section 3);
      * the stub answers exactly two calls, Pass 1 and Pass 2, both on
        `anthropic-direct`;
      * after the key is removed, a re-derivation STOPS (asserted directly below as
        a precondition — it proves the removal took, which `.env`'s
        `override=True` could otherwise undo);
      * the cache hit still renders the public-API label, with no new call. The
        label was recorded when the extraction ran (P9b step 6).
    """
    pdf = make_pdf(tmp_path)
    llm_calls = install_route_a_stub(monkeypatch, pdf)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-no-call-is-made")
    files = _route_a_files(pdf)

    assumptions = closed_client.get(
        "/assumptions", params={"ticker": TICKER, "company_name": COMPANY, "files": files},
    )
    assert error_text(assumptions.text) is None, error_text(assumptions.text)
    assert llm_calls == ["pass1", "pass2"]
    rows = label_rows(assumptions.text)
    assert rows is not None
    assert "public API" in rows["Transport"]
    assert "ANTHROPIC_API_KEY" in rows["Credential source"]

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ValueError, match="No Anthropic credential resolved"):
        resolve_provider("claude", None)

    response = closed_client.post("/valuation", data=VALUATION_FORM | {"files": files})

    assert response.status_code == 200
    assert error_text(response.text) is None, error_text(response.text)
    assert llm_calls == ["pass1", "pass2"]  # no new call: the cache answered
    rows = label_rows(response.text)
    assert rows is not None
    assert "public API" in rows["Transport"]
    assert "ANTHROPIC_API_KEY" in rows["Credential source"]
    assert "Claude Code session" not in text_of(response.text)
    assert price_calls == [(TICKER, 5, "monthly")]


def test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential(
    closed_client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No key, empty cache: the extraction must stop before any call.

    Expected: an error naming `ANTHROPIC_API_KEY` (the credential the stop names
    as its first remedy, `docs/8-build/environment.md` section 3), zero calls to
    `_call_llm`, and no label on the page — no extraction ran, so no route may be
    named.
    """
    pdf = make_pdf(tmp_path)
    llm_calls = install_route_a_stub(monkeypatch, pdf)

    response = closed_client.post(
        "/valuation", data=VALUATION_FORM | {"files": _route_a_files(pdf)},
    )

    message = error_text(response.text)
    assert message is not None
    assert "No Anthropic credential resolved" in message
    assert "ANTHROPIC_API_KEY" in message
    assert llm_calls == []
    assert label_rows(response.text) is None


# ===========================================================================
# 6. A request that names no filing stops (backlog item 29)
# ===========================================================================


def test_valuation_with_no_filing_stops_naming_all_three_fields(
    closed_client: TestClient, loader_calls: list,
) -> None:
    """Backlog item 29, closed at `be1c077`. Lock it.

    Expected: an error naming `session_file`, `files` and `file_path` — the three
    parameters `_run_extraction` takes, any one of which would name a filing.
    Nothing is extracted by either route: `_call_llm` and the loader are untouched,
    the price fetch is never reached, and no route label is shown.
    """
    response = closed_client.post("/valuation", data=VALUATION_FORM)

    assert response.status_code == 200
    message = error_text(response.text)
    assert message is not None
    for field in ("session_file", "files", "file_path"):
        assert field in message
    assert loader_calls == []
    assert label_rows(response.text) is None


def test_assumptions_with_files_naming_no_entry_stops_naming_files(
    closed_client: TestClient,
) -> None:
    """Route A, a `files` value that parses to no filing (`","`).

    Expected: an error naming the field `files` and the value given. Rule 3: it
    used to render an empty form with no error (programmer entry, decision table).
    """
    response = closed_client.get("/assumptions", params={"ticker": TICKER, "files": ","})

    message = error_text(response.text)
    assert message is not None
    assert message.startswith("files:")
    assert "','" in message
    assert label_rows(response.text) is None


def test_assumptions_with_a_session_file_that_is_not_there_stops_naming_it(
    closed_client: TestClient, tmp_path: Path,
) -> None:
    """Route B, a `session_file` that names nothing on disk.

    Expected: the error names the path given (the loader's contract: every stop
    names the file).
    """
    missing = (tmp_path / "no_such_session.json").resolve()
    response = closed_client.get("/assumptions", params={"session_file": str(missing)})

    message = error_text(response.text)
    assert message is not None
    assert str(missing) in message
    assert label_rows(response.text) is None


def test_assumptions_with_no_filing_runs_no_extraction_and_names_no_route(
    closed_client: TestClient, loader_calls: list,
) -> None:
    """GET /assumptions with nothing named runs no extraction (both boundaries are
    closed, the loader is spied) and therefore shows no route label (rule 6: a
    page with no extraction names no route). It does NOT assert whether the page
    shows an error: see the tester entry for that open question."""
    response = closed_client.get("/assumptions")

    assert response.status_code == 200
    assert loader_calls == []
    assert label_rows(response.text) is None
    assert routes_valuation._extraction_cache == {}


# ===========================================================================
# 7. A bad session file shows the loader's message
# ===========================================================================


def test_a_session_file_missing_one_pass1_key_renders_the_loaders_message(
    closed_client: TestClient, tmp_path: Path,
) -> None:
    """Remove `sbc` from year 2024's Pass 1 and request the page.

    Expected: 200, and one error naming the file, the year (2024) and the key
    (`sbc`) — the assignment's item 7, and the loader's stop list (P9a step 10).
    No label (no extraction completed), no statements, nothing cached.
    """
    data = session_dict(make_pdf(tmp_path))
    year_2024 = data["filings"][0]["pass1"]["historical_years"][1]
    assert year_2024["year"] == 2024
    del year_2024["sbc"]
    bad = write_session(tmp_path, data, name="session_missing_sbc.json")

    response = closed_client.get("/assumptions", params={"session_file": str(bad)})

    assert response.status_code == 200
    message = error_text(response.text)
    assert message is not None
    assert str(bad) in message
    assert "year 2024" in message
    assert "'sbc'" in message
    assert "absent" in message
    assert label_rows(response.text) is None
    assert "Adjusted Income Statement" not in response.text
    assert routes_valuation._extraction_cache == {}


def test_a_bad_session_file_uploaded_through_the_form_reaches_the_page_named(
    closed_client: TestClient, tmp_path: Path,
) -> None:
    """The same bad file, by the path a user takes: upload, follow the redirect.

    Expected: the message names the SAVED copy under `uploads/session/` and the key.
    """
    data = session_dict(make_pdf(tmp_path))
    del data["filings"][0]["pass1"]["historical_years"][1]["sbc"]
    payload = write_session(tmp_path, data, name="bad.json").read_bytes()

    response = closed_client.post(
        "/upload-session", files={"session_file": ("bad_upload.json", payload)},
    )

    message = error_text(response.text)
    assert message is not None
    saved = (tmp_path / "uploads" / "session" / "bad_upload.json").resolve()
    assert str(saved) in message
    assert "'sbc'" in message


# ===========================================================================
# 8. session_file together with files — the cache-MISS half (already stops)
# ===========================================================================


def test_valuation_with_session_file_and_files_on_a_cache_miss_stops(
    closed_client: TestClient, session_path: Path, loader_calls: list,
) -> None:
    """Rule 3: an input is never silently ignored.

    Expected: an error naming both fields, `session_file` and `files`, and no
    load of the session file. The cache-HIT half is backlog item 52 and is red; it
    is in `test_routes_session_rule3_red.py`.
    """
    form = VALUATION_FORM | {
        "session_file": str(session_path),
        "files": f"{FISCAL_YEAR}:/nonexistent/never-opened.pdf",
    }
    response = closed_client.post("/valuation", data=form)

    message = error_text(response.text)
    assert message is not None
    assert "session_file" in message
    assert "files" in message
    assert loader_calls == []
    assert label_rows(response.text) is None
