"""Storefront API for the local Campus Customs data pack."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

try:
    from .agent import answer_chat
    from .auth import router as auth_router, session_user, check_origin
    from .chat_memory import load_history, save_exchange
    from .models import ChatRequest, ChatResponse, ChatTurn
except ImportError:  # Support `uvicorn main:app` from the backend folder.
    from agent import answer_chat
    from auth import router as auth_router, session_user, check_origin
    from chat_memory import load_history, save_exchange
    from models import ChatRequest, ChatResponse, ChatTurn

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "campus_customs.db"
logger = logging.getLogger(__name__)

app = FastAPI(title="Campus Customs storefront API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(auth_router)


def connect() -> sqlite3.Connection:
    if not DB.is_file():
        raise HTTPException(status_code=503, detail="Local catalogue database is unavailable.")
    connection = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def product_from_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["colors"] = json.loads(item["colors"])
    item["search_tags"] = json.loads(item["search_tags"])
    item["image_url"] = f"/api/products/{item['product_id']}/image"
    if "available_sizes" in item:
        item["available_sizes"] = item["available_sizes"].split(",") if item["available_sizes"] else []
    del item["image_file_path"]
    return item


@app.get("/api/health")
def health() -> dict:
    if not DB.is_file():
        raise HTTPException(status_code=503, detail="Local catalogue database is unavailable.")
    return {"status": "ok", "source": "local SQLite data pack"}


@app.get("/api/products")
def products() -> list[dict]:
    try:
        with connect() as connection:
            rows = connection.execute(
                """SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock,
                          GROUP_CONCAT(CASE WHEN i.quantity > 0 THEN i.size END) AS available_sizes
                   FROM catalogue c LEFT JOIN inventory i ON i.product_id = c.product_id
                   GROUP BY c.product_id ORDER BY c.name"""
            ).fetchall()
        return [product_from_row(row) for row in rows]
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Catalogue could not be read.") from exc


@app.get("/api/products/{product_id}")
def product(product_id: str) -> dict:
    try:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Product not found.")
            stock = connection.execute(
                "SELECT size, quantity FROM inventory WHERE product_id = ? ORDER BY CASE size WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3 WHEN 'L' THEN 4 WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6 ELSE 7 END",
                (product_id,),
            ).fetchall()
        return {**product_from_row(row), "inventory": [dict(item) for item in stock]}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product could not be read.") from exc


@app.get("/api/products/{product_id}/image")
def product_image(product_id: str) -> FileResponse:
    try:
        with connect() as connection:
            row = connection.execute(
                "SELECT image_file_path FROM catalogue WHERE product_id = ?", (product_id,)
            ).fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product image lookup failed.") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    image = (DATA / row["image_file_path"]).resolve()
    if not image.is_relative_to((DATA / "products").resolve()) or not image.is_file():
        raise HTTPException(status_code=404, detail="Product image unavailable.")
    return FileResponse(image)


@app.get("/api/chat/history", response_model=list[ChatTurn])
def chat_history(request: Request) -> list[ChatTurn]:
    user = session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Log in to load saved chat history.")
    try:
        return load_history(user["id"])
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Saved chat history is unavailable.") from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    check_origin(request)
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be blank.")
    try:
        user = session_user(request)
        history = load_history(user["id"], limit=12) if user else payload.history
        response = await answer_chat(payload.message, history, customer=user, page=payload.page)
        if user:
            save_exchange(user["id"], payload.message.strip(), response)
        return response
    except RuntimeError as exc:
        if "PORTKEY_API_KEY is missing" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        logger.exception("Chat runtime error")
        raise HTTPException(status_code=502, detail="Shop assistant is unavailable. Please try again.") from exc
    except (OSError, sqlite3.Error) as exc:
        logger.exception("Chat data access failed")
        raise HTTPException(status_code=503, detail="Local catalogue is unavailable to the shop assistant.") from exc
    except Exception as exc:
        logger.exception("Chat model call failed")
        raise HTTPException(status_code=502, detail="Shop assistant could not respond. Check the Portkey setup or try again.") from exc
