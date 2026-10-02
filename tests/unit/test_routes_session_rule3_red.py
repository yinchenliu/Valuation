"""RED ON PURPOSE: backlog item 52. Excluded from the gate by its `*_rule3_red.py` name.

**The requirement.** `POST /valuation` given BOTH a `session_file` and `files` must
stop, naming both fields, whether or not the session file's extraction is cached.
Rule 3: an input is never silently ignored. The cache-miss path already stops
(`_run_extraction`, `api/routes_valuation.py:177-182`; locked green in
`test_routes_session.py::test_valuation_with_session_file_and_files_on_a_cache_miss_stops`).

**Why it is red at `be1c077`.** On a cache hit the route looks the key up as
`session_file or files` (`api/routes_valuation.py:544`) BEFORE `_run_extraction`'s
check runs, so the cached session extraction is valued and `files` is dropped
without a word. Found by the `P9b` review as F1, recorded as backlog item 52.

**When it goes green, move it into `test_routes_session.py` in the same unit**
(backlog item 24: a green test left inside this pattern is a test the gate never runs).

Expected values: the field names are the two form parameters `run_valuation`
declares. Nothing was read off a rendered page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from tests.unit._session_route_helpers import (
    FISCAL_YEAR,
    VALUATION_FORM,
    error_text,
    install_price_stub,
    make_pdf,
    open_closed_client,
    session_dict,
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


def test_valuation_with_session_file_and_files_on_a_cache_hit_stops(
    closed_client: TestClient, tmp_path: Path, price_calls: list,
) -> None:
    session_path = write_session(tmp_path, session_dict(make_pdf(tmp_path)))

    # Cache the session file's extraction, as the assumptions page does.
    assumptions = closed_client.get("/assumptions", params={"session_file": str(session_path)})
    assert error_text(assumptions.text) is None

    form = VALUATION_FORM | {
        "session_file": str(session_path),
        "files": f"{FISCAL_YEAR}:/nonexistent/never-opened.pdf",
    }
    response = closed_client.post("/valuation", data=form)

    # Expected: a stop naming both fields, as on the cache miss; and so no price
    # fetched, because the run must stop before it values anything.
    message = error_text(response.text)
    assert message is not None, "a session_file sent with files was valued, files ignored"
    assert "session_file" in message
    assert "files" in message
    assert price_calls == []
