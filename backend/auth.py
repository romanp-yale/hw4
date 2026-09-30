"""Local account and cookie-session endpoints."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

DB = Path(__file__).resolve().parents[1] / "data" / "campus_customs.db"
SESSION_COOKIE = "campus_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
PBKDF2_ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}

router = APIRouter(prefix="/api/auth", tags=["accounts"])


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def connect() -> sqlite3.Connection:
    if not DB.is_file():
        raise HTTPException(status_code=503, detail="Local account database is unavailable.")
    connection = sqlite3.connect(DB, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_sessions(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )"""
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if not parts or parts[0] != "pbkdf2_sha256":
        return False
    try:
        if len(parts) == 3:
            # Format present in the supplied starter database.
            _, salt, expected = parts
            iterations = LEGACY_ITERATIONS
            salt_bytes = salt.encode("utf-8")
        elif len(parts) == 4:
            _, iterations_text, salt, expected = parts
            iterations = int(iterations_text)
            if not 1 <= iterations <= 2_000_000:
                return False
            salt_bytes = bytes.fromhex(salt)
        else:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt_bytes, iterations
        )
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, OverflowError):
        return False


def public_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "name": row["name"],
        "email": row["email"],
    }


def session_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        with connect() as connection:
            row = connection.execute(
                """SELECT u.id, u.name, u.first_name, u.last_name, u.email
                   FROM auth_sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = ? AND s.expires_at > ?""",
                (token_hash, int(time.time())),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    return public_user(row) if row else None


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin is not allowed.")


def create_session(connection: sqlite3.Connection, response: Response, user_id: int) -> None:
    ensure_sessions(connection)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = int(time.time())
    connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
    connection.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, now + SESSION_SECONDS),
    )
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_SECONDS, path="/", httponly=True,
        samesite="lax", secure=os.getenv("COOKIE_SECURE") == "1",
    )


@router.post("/register", status_code=201)
def register(payload: RegisterIn, request: Request, response: Response) -> dict:
    check_origin(request)
    email = str(payload.email).strip().lower()
    try:
        with connect() as connection:
            if connection.execute(
                "SELECT 1 FROM users WHERE lower(email) = ?", (email,)
            ).fetchone():
                raise HTTPException(status_code=409, detail="An account with this email already exists.")
            cursor = connection.execute(
                "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                (f"{payload.first_name} {payload.last_name}", payload.first_name,
                 payload.last_name, email, hash_password(payload.password)),
            )
            row = connection.execute(
                "SELECT id, name, first_name, last_name, email FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            create_session(connection, response, row["id"])
        return {"user": public_user(row)}
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Account could not be created.") from exc


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response) -> dict:
    check_origin(request)
    try:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE lower(email) = ?",
                (str(payload.email).strip().lower(),),
            ).fetchone()
            if row is None or not verify_password(payload.password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid email or password.")
            if len(row["password_hash"].split("$")) == 3:
                connection.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(payload.password), row["id"]),
                )
            create_session(connection, response, row["id"])
        return {"user": public_user(row)}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Login is temporarily unavailable.") from exc


@router.get("/me")
def me(request: Request) -> dict:
    user = session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"user": user}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    check_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            with connect() as connection:
                connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
        except sqlite3.Error as exc:
            raise HTTPException(status_code=503, detail="Logout is temporarily unavailable.") from exc
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
