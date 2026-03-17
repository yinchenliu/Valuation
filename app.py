"""FastAPI application entry point for the Valuation Platform."""

import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes_upload import router as upload_router
from api.routes_valuation import router as valuation_router
from config import BASE_DIR

app = FastAPI(title="DCF Valuation Platform", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Register routes
app.include_router(upload_router)
app.include_router(valuation_router)
