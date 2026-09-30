"""Append-only logical JSON event log for shopping-agent runs and tools."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
from pathlib import Path
from threading import Lock
from typing import Any, Callable

AUDIT_FILE = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
_lock = Lock()


def _safe(value: Any) -> str:
    text = str(value)[:80]
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", text)
    text = re.sub(r"(?i)(?:sk-|pk-|password|api[_-]?key)[^\s,;]*", "[redacted]", text)
    return text


def record_event(tool_name: str, arguments: dict[str, Any], result: dict[str, Any], stop_reason: str) -> None:
    """Append one event without discarding prior runs; never log raw chat text or identity."""
    event = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
        "stop_reason": stop_reason,
    }
    with _lock:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        entries = json.loads(AUDIT_FILE.read_text(encoding="utf-8")) if AUDIT_FILE.exists() else []
        if not isinstance(entries, list):
            raise ValueError("Audit trail must be a JSON array; existing entries were preserved.")
        entries.append(event)
        temporary = AUDIT_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, AUDIT_FILE)


def audited_tool(function: Callable) -> Callable:
    """Keep the agent's tool signature while recording a short call/result event."""
    parameters = signature(function)

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bound = parameters.bind(*args, **kwargs)
        info = {
            key: {"chars": len(str(value))} if key in {"query", "color"} else _safe(value)
            for key, value in bound.arguments.items()
        }
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            record_event(function.__name__, info, {"error_type": type(exc).__name__}, "tool_error")
            raise
        if isinstance(result, list):
            outcome = {"count": len(result), "product_ids": [getattr(item, "product_id", None) for item in result[:3]]}
        elif result is None:
            outcome = {"found": False}
        else:
            outcome = {"found": True, "product_id": getattr(result, "product_id", None),
                       "status": getattr(result, "status", None), "quantity": getattr(result, "quantity", None)}
        record_event(function.__name__, info, outcome, "tool_returned")
        return result

    return wrapped
