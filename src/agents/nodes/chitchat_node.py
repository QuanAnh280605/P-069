"""Chitchat node: answer general questions in natural Vietnamese."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI của hệ thống AI Semantic Layer Agent — "
    "một nền tảng giúp doanh nghiệp tự động phân tích cấu trúc database, "
    "đặt tên nghiệp vụ tiếng Việt và sinh Business Metrics (chỉ số kinh doanh).\n\n"
    "Quy tắc quan trọng: BẠN PHẢI TỪ CHỐI TRẢ LỜI những câu hỏi hoặc chủ đề KHÔNG LIÊN QUAN đến dữ liệu, cơ sở dữ liệu, chỉ số kinh doanh, lập trình, hoặc các tính năng của hệ thống. "
    "Trong trường hợp này, hãy lịch sự giải thích rằng bạn chỉ hỗ trợ các nghiệp vụ về dữ liệu.\n\n"
    "Hãy trả lời thân thiện, ngắn gọn và bằng tiếng Việt. "
    "Nếu được hỏi về tính năng, hãy giới thiệu những gì hệ thống làm được."
)

_FALLBACK_RESPONSE = "Xin lỗi, tôi không thể phản hồi lúc này. Vui lòng thử lại!"


async def chitchat_node(state: AgentState) -> dict[str, Any]:
    """Generate a friendly natural-language response to chitchat messages.

    Uses a higher temperature (0.7) for more natural, human-like responses.
    """
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"chat_response": "Xin chào! Tôi có thể giúp gì cho bạn?"}

    try:
        llm = get_llm()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        # Increase temperature for more natural chitchat responses
        llm.temperature = 0.7  # type: ignore[attr-defined]
        response = await llm.ainvoke(messages)
        reply = (response.content if hasattr(response, "content") else str(response)).strip()
        logger.info("Chitchat node replied (len=%d chars)", len(reply))
        return {"chat_response": reply}

    except Exception as exc:
        logger.warning("Chitchat node failed: %s", exc)
        return {"chat_response": _FALLBACK_RESPONSE}
