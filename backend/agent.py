"""PydanticAI model setup, instructions, tools, and chat execution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

try:
    from .audit import audited_tool, record_event
    from .models import AgentReply, ChatResponse, ChatTurn, PageContext
    from .tools import find_in_stock_products, find_products_by_color, get_product_details, get_stock_by_size, product_cards, search_products
except ImportError:  # Support `uvicorn main:app` from the backend folder.
    from audit import audited_tool, record_event
    from models import AgentReply, ChatResponse, ChatTurn, PageContext
    from tools import find_in_stock_products, find_products_by_color, get_product_details, get_stock_by_size, product_cards, search_products

PROJECT = Path(__file__).resolve().parents[1]
PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "prompt.md"
for folder in (PROJECT, *PROJECT.parents):
    load_dotenv(folder / ".env", override=False)

MODEL_NAME = os.getenv("PORTKEY_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")


@dataclass
class ChatDeps:
    customer: dict | None
    page: PageContext | None
    current_product_id: str | None
    current_product_name: str | None


def reasoning_effort(message: str) -> str:
    text = message.casefold().strip()
    if text in {"hi", "hello", "hey", "thanks", "thank you"}:
        return "low"
    if len(text) > 300 or any(word in text for word in ("compare", "versus", "vs.", "which is best", "difference between")):
        return "high"
    return "medium"


@lru_cache(maxsize=1)
def get_agent() -> Agent[ChatDeps, AgentReply]:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Add it to an ignored .env or the environment.")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key},
    )
    model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    agent = Agent(
        model,
        output_type=AgentReply,
        deps_type=ChatDeps,
        instructions=PROMPT_FILE.read_text(encoding="utf-8"),
    )

    @agent.instructions
    def runtime_context(ctx: RunContext[ChatDeps]) -> str:
        customer = ctx.deps.customer
        identity = (
            f"Authenticated customer: name={customer['name']!r}; email={customer['email']!r}. "
            "Use this only for a helpful greeting or account identity; do not expose it to anyone else."
            if customer else "Guest shopper; no customer identity is available."
        )
        page = ctx.deps.page
        if ctx.deps.current_product_id:
            page_text = (
                f"Current page: product detail for {ctx.deps.current_product_name!r}, "
                f"product_id={ctx.deps.current_product_id!r}. Resolve 'this' and 'it' to this product "
                "unless the conversation clearly refers to another item. Use product tools for its colors, price, or stock."
            )
        else:
            page_text = f"Current page: {page.kind if page else 'unknown'}. No current product is established."
        return f"{identity}\n{page_text}"
    for function in (search_products, get_product_details, get_stock_by_size,
                     find_products_by_color, find_in_stock_products):
        agent.tool_plain(audited_tool(function), name=function.__name__, description=function.__doc__)
    return agent


async def answer_chat(message: str, history: list[ChatTurn], customer: dict | None = None, page: PageContext | None = None) -> ChatResponse:
    current_product = get_product_details(page.product_id) if page and page.kind == "product" and page.product_id else None
    deps = ChatDeps(
        customer=customer, page=page,
        current_product_id=current_product.product_id if current_product else None,
        current_product_name=current_product.name if current_product else None,
    )
    prior = []
    for turn in history[-12:]:
        if turn.role == "user":
            prior.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            prior.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    call_info = {"message_chars": len(message), "history_turns": len(prior),
                 "page_kind": page.kind if page else "unknown", "authenticated": customer is not None}
    try:
        result = await get_agent().run(
            message.strip(),
            message_history=prior,
            deps=deps,
            model_settings=OpenAIResponsesModelSettings(
                openai_reasoning_effort=reasoning_effort(message)
            ),
            usage_limits=UsageLimits(request_limit=8, tool_calls_limit=12),
        )
        response = ChatResponse(
            reply=result.output.reply,
            products=(
                product_cards([item.product_id for item in search_products(result.output.search_query, limit=30)], limit=30)
                if result.output.search_query
                else product_cards(result.output.product_ids)
            ),
            search_query=result.output.search_query,
            model=MODEL_NAME,
        )
    except Exception as exc:
        record_event("agent_loop", call_info, {"error_type": type(exc).__name__}, "error")
        raise
    record_event("agent_loop", call_info,
                 {"reply_chars": len(response.reply), "product_cards": len(response.products)}, "completed")
    return response
