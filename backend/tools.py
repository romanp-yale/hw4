"""Read-only, parameterized database tools available to the shopping agent."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

try:
    from .models import ProductCard, ProductEvidence, SizeStockLookup, StockItem
except ImportError:  # Support `uvicorn main:app` from the backend folder.
    from models import ProductCard, ProductEvidence, SizeStockLookup, StockItem

DATA = Path(__file__).resolve().parents[1] / "data"
DB = DATA / "campus_customs.db"


def _terms(query: str) -> list[str]:
    aliases = {"hoodies": "hoodie", "tees": "t-shirt", "tshirts": "t-shirt", "sweatshirts": "sweatshirt", "jackets": "jacket"}
    return [aliases.get(term, term) for term in re.findall(r"[\w-]+", query.casefold()) if len(term) > 2][:8]


def _score(row: sqlite3.Row, terms: list[str]) -> int:
    name = row["name"].casefold()
    kind = row["garment_type"].casefold()
    tags = row["search_tags"].casefold()
    description = row["description"].casefold()
    return sum(
        (4 if term in name else 0) + (3 if term in kind else 0)
        + (2 if term in tags else 0) + (1 if term in description else 0)
        for term in terms
    )


def _ranked(rows: list[sqlite3.Row], query: str) -> list[sqlite3.Row]:
    terms = _terms(query)
    if not terms:
        return []
    scored = [(_score(row, terms), row) for row in rows]
    return [row for score, row in sorted(scored, key=lambda pair: (-pair[0], pair[1]["name"])) if score]


def _normalize_size(size: str) -> str:
    aliases = {
        "EXTRA SMALL": "XS", "SMALL": "S", "MEDIUM": "M", "LARGE": "L",
        "EXTRA LARGE": "XL", "EXTRA EXTRA LARGE": "XXL", "2XL": "XXL",
    }
    return aliases.get(size.strip().upper(), size.strip().upper())


def _connect() -> sqlite3.Connection:
    if not DB.is_file():
        raise FileNotFoundError("Local catalogue database is unavailable.")
    connection = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _evidence(connection: sqlite3.Connection, row: sqlite3.Row) -> ProductEvidence:
    stock = connection.execute(
        "SELECT size, quantity FROM inventory WHERE product_id = ?",
        (row["product_id"],),
    ).fetchall()
    return ProductEvidence(
        product_id=row["product_id"], name=row["name"],
        garment_type=row["garment_type"], description=row["description"],
        colors=json.loads(row["colors"]), price=row["price"],
        inventory=[StockItem(
            size=item["size"], quantity=item["quantity"],
            availability="in_stock" if item["quantity"] > 0 else "out_of_stock",
        ) for item in stock],
    )


def search_products(query: str, limit: int = 5) -> list[ProductEvidence]:
    """Find products by shopper terms; includes database price and size stock."""
    if not _terms(query):
        return []
    with _connect() as connection:
        rows = connection.execute(
            "SELECT product_id, name, garment_type, description, colors, search_tags, price FROM catalogue"
        ).fetchall()
        return [_evidence(connection, row) for row in _ranked(rows, query)[: max(1, min(limit, 30))]]


def find_products_by_color(color: str, query: str = "", limit: int = 5) -> list[ProductEvidence]:
    """Return only products whose catalogue color list contains the requested color."""
    requested = color.strip().casefold()
    if not requested:
        return []
    with _connect() as connection:
        rows = connection.execute(
            "SELECT product_id, name, garment_type, description, colors, search_tags, price FROM catalogue"
        ).fetchall()
        matching = [row for row in rows if any(
            requested in listed.casefold() for listed in json.loads(row["colors"])
        )]
        ordered = _ranked(matching, query) if query.strip() else sorted(matching, key=lambda row: row["name"])
        return [_evidence(connection, row) for row in ordered[: max(1, min(limit, 8))]]


def find_in_stock_products(query: str, size: str, limit: int = 5) -> list[ProductEvidence]:
    """Return matching products with a positive database quantity in this exact size."""
    if not _terms(query):
        return []
    normalized_size = _normalize_size(size)
    with _connect() as connection:
        rows = connection.execute(
            """SELECT c.product_id, c.name, c.garment_type, c.description, c.colors,
                      c.search_tags, c.price FROM catalogue c
               JOIN inventory i ON i.product_id = c.product_id
               WHERE upper(i.size) = ? AND i.quantity > 0""",
            (normalized_size,),
        ).fetchall()
        return [_evidence(connection, row) for row in _ranked(rows, query)[: max(1, min(limit, 8))]]


def get_product_details(product_id: str) -> ProductEvidence | None:
    """Read one exact product and its size-level stock from SQLite."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT product_id, name, garment_type, description, colors, price FROM catalogue WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return _evidence(connection, row) if row else None


def get_stock_by_size(product_id: str, size: str) -> SizeStockLookup:
    """Check one exact product/size. Zero units means out of stock; absent rows are not listed."""
    requested_size = size.strip()
    normalized_size = _normalize_size(requested_size)
    with _connect() as connection:
        product = connection.execute(
            "SELECT name, price FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if product is None:
            return SizeStockLookup(
                product_id=product_id, product_name=None, requested_size=requested_size,
                size=normalized_size, quantity=None, status="product_not_found", price=None,
            )
        stock = connection.execute(
            "SELECT quantity FROM inventory WHERE product_id = ? AND upper(size) = ?",
            (product_id, normalized_size),
        ).fetchone()
    quantity = stock["quantity"] if stock else None
    status = (
        "size_not_listed" if quantity is None else
        "out_of_stock" if quantity == 0 else "in_stock"
    )
    return SizeStockLookup(
        product_id=product_id, product_name=product["name"],
        requested_size=requested_size, size=normalized_size,
        quantity=quantity, status=status, price=product["price"],
    )


def product_cards(product_ids: list[str], limit: int = 4) -> list[ProductCard]:
    """Hydrate model-selected IDs from SQLite, dropping unknown IDs."""
    cards: list[ProductCard] = []
    seen: set[str] = set()
    with _connect() as connection:
        for product_id in product_ids[: max(1, min(limit, 30))]:
            if product_id in seen:
                continue
            seen.add(product_id)
            row = connection.execute(
                "SELECT product_id, name, garment_type, description, price FROM catalogue WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            if row:
                cards.append(ProductCard(
                    **dict(row), image_url=f"/api/products/{row['product_id']}/image"
                ))
    return cards
