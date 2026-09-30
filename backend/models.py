"""Validated chat API, agent output, and product evidence types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3000)


class PageContext(BaseModel):
    kind: Literal["home", "products", "product", "about", "account", "other"]
    product_id: str | None = Field(default=None, max_length=120)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    page: PageContext | None = None


class StockItem(BaseModel):
    size: str
    quantity: int = Field(ge=0)
    availability: Literal["in_stock", "out_of_stock"]


class SizeStockLookup(BaseModel):
    product_id: str
    product_name: str | None
    requested_size: str
    size: str
    quantity: int | None = Field(ge=0)
    status: Literal["in_stock", "out_of_stock", "size_not_listed", "product_not_found"]
    price: float | None = Field(ge=0)


class ProductEvidence(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    price: float = Field(ge=0)
    inventory: list[StockItem]


class ProductCard(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    price: float = Field(ge=0)
    image_url: str


class AgentReply(BaseModel):
    reply: str = Field(min_length=1, max_length=3000)
    product_ids: list[str] = Field(default_factory=list, max_length=4)
    search_query: str | None = Field(default=None, max_length=80)


class ChatResponse(BaseModel):
    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    search_query: str | None = None
    model: str
