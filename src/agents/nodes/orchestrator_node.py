"""Orchestrator node: classify user intent for multi-agent routing."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """Bạn là bộ phân loại câu hỏi thông minh.
Phân loại câu hỏi của người dùng vào đúng 1 trong 2 nhóm:

- "chitchat": chào hỏi, hỏi thông tin chung về hệ thống, câu hỏi không liên quan đến dữ liệu
- "metric_query": hỏi về chỉ số kinh doanh, doanh thu, công thức tính toán, đề xuất metric, phân tích dữ liệu

Chỉ trả về DUY NHẤT 1 từ: "chitchat" hoặc "metric_query"

Câu hỏi: {user_message}"""


async def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """Classify user message into 'chitchat' or 'metric_query'.

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
        prompt = _CLASSIFY_PROMPT.format(user_message=user_message)
        response = await llm.ainvoke(prompt)
        raw = (response.content if hasattr(response, "content") else str(response)).strip().lower()

        # Extract intent — accept exact match or substring
        intent = "metric_query" if "metric_query" in raw else "chitchat"
        logger.info(
            "Orchestrator classified message (len=%d) → intent=%s",
            len(user_message),
            intent,
        )
        return {"intent": intent}

    except Exception as exc:
        logger.warning("Orchestrator classification failed, defaulting to chitchat: %s", exc)
        return {"intent": "chitchat"}
