"""Persistent chat turns for authenticated customers only."""

from __future__ import annotations

import json
import sqlite3

try:
    from .auth import connect
    from .models import ChatResponse, ChatTurn
except ImportError:
    from auth import connect
    from models import ChatResponse, ChatTurn


def load_history(user_id: int, limit: int = 50) -> list[ChatTurn]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT role, content FROM chat_messages
               WHERE user_id = ? AND role IN ('user', 'assistant')
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [ChatTurn(role=row["role"], content=row["content"]) for row in reversed(rows)]


def save_exchange(user_id: int, message: str, response: ChatResponse) -> None:
    product_ids = [product.product_id for product in response.products]
    with connect() as connection:
        connection.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
            (user_id, message),
        )
        connection.execute(
            """INSERT INTO chat_messages (user_id, role, content, products_json)
               VALUES (?, 'assistant', ?, ?)""",
            (user_id, response.reply, json.dumps(product_ids)),
        )
