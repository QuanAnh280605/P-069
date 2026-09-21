"""Chitchat node: answer general questions in natural Vietnamese."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI của hệ thống AI Semantic Layer Agent — "
    "nền tảng giúp doanh nghiệp tự động phân tích cấu trúc database, "
    "đặt tên nghiệp vụ tiếng Việt và quản lý Business Metrics.\n\n"
    "Nhiệm vụ của bạn:\n"
    "- Chào hỏi, cảm ơn hoặc giải thích các tính năng của hệ thống một cách thân thiện, ngắn gọn bằng tiếng Việt.\n"
    "- BẮT BUỘC TỪ CHỐI mọi câu hỏi hoặc chủ đề KHÔNG LIÊN QUAN đến dữ liệu, cơ sở dữ liệu, schema, chỉ số kinh doanh hay tính năng hệ thống (ví dụ: thời tiết, đời sống, nấu ăn, giải trí, kiến thức phổ thông, lập trình ngoài lề, v.v.).\n"
    "- Khi từ chối, hãy giải thích lịch sự rằng bạn chỉ hỗ trợ các nghiệp vụ về dữ liệu doanh nghiệp và Semantic Layer, sau đó hướng người dùng đặt câu hỏi về database hoặc metrics."
)

_FALLBACK_RESPONSE = "Xin lỗi, tôi không thể phản hồi lúc này. Vui lòng thử lại!"
_MAX_HISTORY_CHARS = 6000


async def chitchat_node(state: AgentState) -> dict[str, Any]:
    """Generate a friendly natural-language response to chitchat messages.

    Uses the shared deterministic LLM configuration.
    """
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"chat_response": "Xin chào! Tôi có thể giúp gì cho bạn?"}

    try:
        llm = get_llm()
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        messages.extend(_history_messages(state.get("chat_history", [])))
        messages.append({"role": "user", "content": user_message})
        response = await llm.ainvoke(messages)
        reply = (response.content if hasattr(response, "content") else str(response)).strip()
        logger.info("Chitchat node replied (len=%d chars)", len(reply))
        return {"chat_response": reply}

    except Exception as exc:
        logger.warning("Chitchat node failed: %s", exc)
        return {"chat_response": _FALLBACK_RESPONSE}


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
