"""
PaperTerrace - AI-powered paper reading assistant
Main application entry point.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers import (
    analysis_router,
    auth_router,
    chat_router,
    explore_router,
    note_router,
    papers_router,
    pdf_router,
    translation_router,
    users_router,
)

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="PaperTerrace",
    description="AI-powered paper reading assistant",
    version="1.0.0",
)

# Firebase Config for Frontend
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
}

# Templates and static files
templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# ============================================================================
# Include all routers
# ============================================================================

# Auth & Users
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(explore_router)

# PDF Analysis & Streaming
app.include_router(pdf_router)

# Translation & Dictionary
app.include_router(translation_router)

# Chat
app.include_router(chat_router)

# Analysis Features
app.include_router(analysis_router)

# Notes
app.include_router(note_router)

# Paper Management
app.include_router(papers_router)


# ============================================================================
# Main Page
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "firebase_config": FIREBASE_CONFIG}
    )
