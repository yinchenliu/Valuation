"""File upload routes for 10-K/10-Q PDF filings."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, UPLOAD_DIR

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _save_upload(file: UploadFile, ticker: str) -> Path:
    """Save an uploaded file to the uploads directory."""
    ticker_dir = UPLOAD_DIR / ticker.upper()
    ticker_dir.mkdir(parents=True, exist_ok=True)
    dest = ticker_dir / file.filename
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
    return templates.TemplateResponse("upload.html", {"request": request})


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
