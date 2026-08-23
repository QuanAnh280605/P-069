"""Read-only data guidance node for Workspace members and Data Leads."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Bạn là Data Assistant của AI Semantic Layer Agent.
Chỉ hỗ trợ người dùng hiểu schema, glossary, quan hệ bảng, metric đã được phê duyệt,
và cách chọn Metric/Dimension/Filter để truy vấn an toàn.

Không được tạo, sửa hoặc phê duyệt metric. Không viết SQL tự do, không đoán dữ liệu
không có trong context, không tiết lộ connection string hay thông tin bí mật.
Nếu người dùng yêu cầu tạo metric, hãy giải thích rằng Metric Studio chỉ dành cho Data Lead
và hướng họ sang việc tìm hiểu metric đã approved hoặc yêu cầu Data Lead hỗ trợ.
Trả lời ngắn gọn, rõ ràng bằng tiếng Việt. Luôn dùng Markdown sáng sủa: mỗi ý chính xuống dòng,
dùng danh sách đánh số/gạch đầu dòng, code inline cho tên bảng/cột, và nếu dùng bảng thì phải là
GFM table hợp lệ có dòng trống trước và sau. Không nối nhiều ý vào một đoạn dài."""


_MAX_HISTORY_CHARS = 10000


async def data_assistant_node(state: AgentState) -> dict[str, Any]:
    """Answer read-only schema and approved-metric questions with chat history context."""
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"intent": "data_question", "chat_response": "Bạn muốn tìm hiểu phần dữ liệu nào?"}
    context = _format_context(state.get("enriched_schema", {}), state.get("approved_metrics", []))
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "system", "content": f"Context semantic layer được phép đọc:\n{context}"},
    ]
    messages.extend(_history_messages(state.get("chat_history", [])))
    messages.append({"role": "user", "content": user_message})
    try:
        response = await get_llm().ainvoke(messages)
        reply = (response.content if hasattr(response, "content") else str(response)).strip()
        return {"intent": "data_question", "chat_response": reply}
    except Exception as exc:
        logger.warning("Data assistant failed: %s", exc)
        return {"intent": "data_question", "chat_response": "Không thể đọc semantic layer lúc này."}


def _history_messages(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize prior messages and keep the prompt within a bounded budget."""
    result: list[dict[str, str]] = []
    remaining = _MAX_HISTORY_CHARS
    for item in reversed(history):
        role = item.get("role")
        content = item.get("content", "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        content = content[-remaining:]
        result.append({"role": role, "content": content})
        remaining -= len(content)
        if remaining <= 0:
            break
    result.reverse()
    return result


def _format_context(schema: dict[str, Any], metrics: list[dict[str, Any]]) -> str:
    """Serialize bounded semantic context without exposing connection details."""
    payload = {"schema": schema, "approved_metrics": metrics}
    return json.dumps(payload, ensure_ascii=False, default=str)[:14000]
