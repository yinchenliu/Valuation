"""File upload routes for 10-K/10-Q PDF filings."""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, UPLOAD_DIR

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(raw: str, fallback: str = "filing.pdf") -> str:
    """Reduce a client-supplied filename to a plain basename.

    The uploaded name is attacker-controlled: it can contain directory
    separators, '..', a drive letter, or a NUL. Everything except the final path
    component is discarded and the remainder is restricted to a conservative
    character set, so a write can never escape the ticker's upload directory.
    """
    name = unicodedata.normalize("NFKD", raw or "")
    # Take the last component under both separators, then strip any drive prefix.
    name = name.replace("\\", "/").split("/")[-1]
    name = name.split(":")[-1]
    name = _SAFE_NAME.sub("_", name).strip("._")
    if not name or name in {".", ".."}:
        return fallback
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:120]


def _save_upload(file: UploadFile, ticker: str) -> Path:
    """Save an uploaded file into the ticker's upload directory."""
    ticker_dir = UPLOAD_DIR / _SAFE_NAME.sub("_", ticker.upper())[:20]
    ticker_dir.mkdir(parents=True, exist_ok=True)

    dest = ticker_dir / _safe_filename(file.filename or "")
    # Belt and braces: confirm the resolved path really is inside the directory.
    if ticker_dir.resolve() not in dest.resolve().parents:
        raise ValueError(f"Refusing to write outside the upload directory: {file.filename!r}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _guess_fiscal_year(filename: str) -> int | None:
    """Try to extract a 4-digit year from the filename."""
    match = re.search(r"(20\d{2})", filename)
    return int(match.group(1)) if match else None


@router.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the file upload page."""
    return templates.TemplateResponse(request, "upload.html", {})


@router.post("/upload")
async def upload_files(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    pdf_files: list[UploadFile] = File(...),
):
    """Handle upload of one or more 10-K/10-Q PDF filings."""
    file_paths = []
    for f in pdf_files:
        path = _save_upload(f, ticker)
        year = _guess_fiscal_year(f.filename or "")
        file_paths.append((year, str(path)))

    # Pass file info as comma-separated "year:path" pairs.
    file_params = ",".join(f"{year or 0}:{path}" for year, path in file_paths)

    # urlencode, so Windows paths (backslashes, spaces, colons) and any '&' in a
    # company name survive the round trip instead of truncating the query string.
    query = urlencode({
        "ticker": ticker.upper(),
        "company_name": company_name,
        "files": file_params,
    })

    return RedirectResponse(url=f"/assumptions?{query}", status_code=303)
