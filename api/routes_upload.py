"""File upload routes: 10-K/10-Q PDF filings (route A) and session files (route B)."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, UPLOAD_DIR
from ingestion.filings import fiscal_year_from_filename, verify_filing_years

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _save_upload(file: UploadFile, ticker: str) -> Path:
    """Save an uploaded file to the uploads directory."""
    # Moved here from config.py, which used to run this at import time.
    # The directory is created when a file actually arrives, not when a
    # configuration module is imported.
    UPLOAD_DIR.mkdir(exist_ok=True)
    ticker_dir = UPLOAD_DIR / ticker.upper()
    ticker_dir.mkdir(parents=True, exist_ok=True)
    dest = ticker_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _save_session_upload(file: UploadFile) -> Path:
    """Save an uploaded session file under uploads/session/, as `_save_upload` saves a PDF.

    It is not parsed here. `load_session_extraction` is the one reader of the
    format, and it runs at /assumptions, where its message reaches the page.

    A missing filename stops, naming the field (rule 3). `_save_upload` above
    uses `file.filename` as a path segment unchecked (backlog item 28); that
    pattern is not copied. Only the final path component of the name is kept,
    so a crafted name such as "../x.json" cannot write outside the directory.
    """
    name = Path(file.filename).name if file.filename else ""
    if name in ("", ".", ".."):
        raise HTTPException(
            status_code=400,
            detail=f"session_file: the uploaded file has no usable filename ({file.filename!r}).",
        )
    session_dir = UPLOAD_DIR / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    dest = session_dir / name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _guess_fiscal_year(filename: str) -> int | None:
    """The fiscal year the filename names, or None.

    Not a second guesser: it is `fiscal_year_from_filename`, the one the CLI and
    the session route use (P10c, backlog item 43). The year it gives is verified
    against the filing's content in `upload_files` before anything is extracted.
    """
    return fiscal_year_from_filename(filename)


@router.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the file upload page."""
    # starlette 1.6.0 removed the deprecated TemplateResponse(name, context) form;
    # the signature is (request, name, context). Under the old call the context dict
    # bound to `name`, so this route answered HTTP 500 on every request -- the front
    # page of the web app, unreachable since the first commit this build measured.
    # No context dict is passed because starlette does context.setdefault("request",
    # request) itself, and no template reads anything else here.
    return templates.TemplateResponse(request, "upload.html")


@router.post("/upload")
async def upload_files(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    pdf_files: list[UploadFile] = File(...),
):
    """Handle upload of one or more 10-K/10-Q PDF filings.

    Every year taken from a filename is verified against the filing's cover and
    income statement (`verify_filing_years`). A mismatch, or a filing whose
    evidence cannot be read, re-renders this page with the message (HTTP 400),
    and nothing is extracted: there is no redirect to /assumptions. A file whose
    name carries no year is passed on as year 0 and not verified (backlog
    item 49 owns what happens to it next).
    """
    file_paths = []
    for f in pdf_files:
        path = _save_upload(f, ticker)
        year = _guess_fiscal_year(f.filename or "")
        file_paths.append((year, str(path)))

    try:
        verify_filing_years(
            [(year, path) for year, path in file_paths if year is not None],
            "rename_and_upload",
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "upload.html", {"error": str(exc)}, status_code=400
        )

    # Pass file info as comma-separated "year:path" pairs
    file_params = ",".join(
        f"{year or 0}:{path}" for year, path in file_paths
    )

    return RedirectResponse(
        url=(
            f"/assumptions?ticker={ticker.upper()}"
            f"&company_name={company_name}"
            f"&files={file_params}"
        ),
        status_code=303,
    )


@router.post("/upload-session")
async def upload_session_file(
    session_file: UploadFile = File(...),
):
    """Accept a session file written by a Claude Code session (route B).

    The figures in it were read from the PDFs in a Claude Code session; no API
    call is made on this path. The file is saved and handed to /assumptions by
    path. Parsing, and every stop the loader makes, happens there.
    """
    path = _save_session_upload(session_file)
    return RedirectResponse(
        url="/assumptions?" + urlencode({"session_file": str(path)}),
        status_code=303,
    )
