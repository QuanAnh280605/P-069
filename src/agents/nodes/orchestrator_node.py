"""Orchestrator node: classify user intent for multi-agent routing."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """Bạn là bộ phân loại câu hỏi thông minh.
Phân loại câu hỏi của người dùng vào đúng 1 trong 3 nhóm:

- "chitchat": chào hỏi, hỏi thông tin chung về hệ thống, câu hỏi không liên quan đến dữ liệu
- "data_question": hỏi về schema, bảng, cột, glossary, metric đã có, cách chọn dữ liệu hoặc giải thích kết quả
- "metric_query": yêu cầu tạo/sửa/đề xuất công thức Business Metric mới

Chỉ trả về DUY NHẤT 1 từ: "chitchat", "data_question" hoặc "metric_query"

Câu hỏi trước đây:
{history}

Câu hỏi mới nhất: {user_message}"""


async def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """Classify user message into 'chitchat', 'data_question', or 'metric_query'.

    Uses LLM with temperature=0.0 for deterministic classification.
    Falls back to 'chitchat' on error to avoid breaking the conversation.
    """
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {
            "intent": "chitchat",
            "chat_response": "Bạn chưa nhập câu hỏi. Tôi có thể giúp gì cho bạn?",
        }

    try:
        llm = get_llm()
        history = _format_history(state.get("chat_history", []))
        prompt = _CLASSIFY_PROMPT.format(user_message=user_message, history=history)
        response = await llm.ainvoke(prompt)
        raw = (response.content if hasattr(response, "content") else str(response)).strip().lower()

        # Extract intent — accept exact match or substring
        if "metric_query" in raw:
            intent = "metric_query"
        elif "data_question" in raw:
            intent = "data_question"
        else:
            intent = "chitchat"
        logger.info(
            "Orchestrator classified message (len=%d) → intent=%s",
            len(user_message),
            intent,
        )
        return {"intent": intent}

    except Exception as exc:
        logger.warning("Orchestrator classification failed, defaulting to chitchat: %s", exc)
        return {"intent": "chitchat"}


def _format_history(history: list[dict[str, str]]) -> str:
    """Format a small untrusted history excerpt for intent classification."""
    lines = []
    for item in history[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()[:1000]
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(không có)"
