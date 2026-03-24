"""File upload routes for 10-K/10-Q PDF filings."""

from __future__ import annotations

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


@router.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the file upload page."""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload")
async def upload_files(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    pdf_file: UploadFile = File(...),
):
    """Handle upload of a 10-K/10-Q PDF filing."""
    file_path = _save_upload(pdf_file, ticker)

    # Store file path in session-like query params for the assumptions page
    return RedirectResponse(
        url=(
            f"/assumptions?ticker={ticker.upper()}"
            f"&company_name={company_name}"
            f"&file_path={file_path}"
        ),
        status_code=303,
    )
