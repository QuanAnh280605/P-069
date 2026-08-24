"""Classify chat requests for direct data guidance or metric generation."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_OUT_OF_SCOPE_RESPONSE = (
    "Tôi là trợ lý AI chuyên về Semantic Layer và phân tích dữ liệu doanh nghiệp. "
    "Tôi chỉ hỗ trợ các câu hỏi liên quan đến cơ sở dữ liệu, schema, bảng, cột, "
    "Business Metrics và tính năng của hệ thống. "
    "Rất tiếc tôi không thể trả lời câu hỏi ngoài phạm vi này. "
    "Bạn có câu hỏi nào về dữ liệu không?"
)

_CLASSIFY_PROMPT = """Bạn là bộ phân loại câu hỏi thông minh cho hệ thống AI Semantic Layer.
Phân loại câu hỏi của người dùng vào đúng 1 trong 5 nhóm:

- "semantic_query": Câu hỏi yêu cầu xem số liệu, kết quả, báo cáo, truy vấn, thống kê hoặc tính toán dữ liệu thực tế từ Live Database (ví dụ: "cho tôi kết quả Tổng doanh thu theo từng khách hàng", "Xem kết quả doanh thu", "Tổng doanh thu theo khách hàng năm 2024", "Doanh thu tháng này theo chi nhánh", "Số lượng đơn hàng hoàn thành", "Báo cáo doanh số theo sản phẩm", "Thống kê đơn hàng"). BẤT KỲ CÂU HỎI NÀO YÊU CẦU LẤY SỐ LIỆU/KẾT QUẢ/TÍNH TOÁN ĐỀU THUỘC NHÓM NÀY.
- "metric_query": Yêu cầu tạo mới, chỉnh sửa, xây dựng hoặc đề xuất công thức định nghĩa Business Metric mới vào hệ thống (ví dụ: "Tạo metric mới Doanh thu thuần", "Đề xuất metric cho bảng orders", "Định nghĩa công thức AOV", "Tạo chỉ số tỷ lệ hủy đơn"). CHỈ phân loại vào nhóm này khi người dùng muốn định nghĩa/tạo thêm metric mới vào catalog, KHÔNG phân loại vào đây nếu người dùng muốn xem số liệu/kết quả thực tế.
- "data_question": Hỏi về cấu trúc database, schema, bảng, cột, kiểu dữ liệu, glossary, quan hệ bảng, danh sách metric đã có hoặc hướng dẫn chọn dữ liệu/dimension/filter để tìm hiểu dữ liệu (không yêu cầu lấy số liệu cụ thể).
- "chitchat": Chào hỏi (xin chào, cảm ơn, tạm biệt), hỏi về danh tính/khả năng của AI trợ lý hoặc hỏi thông tin/tính năng chung của hệ thống AI Semantic Layer.
- "out_of_scope": Câu hỏi hoặc yêu cầu KHÔNG LIÊN QUAN đến dữ liệu, database, Business Metrics hay tính năng hệ thống (ví dụ: thời tiết, công thức nấu ăn, viết thơ, kể chuyện, giải toán ngoài lề, tin tức xã hội, thể thao, giải trí, lập trình ứng dụng ngoài lề...).

Chỉ trả về DUY NHẤT 1 từ trong 5 từ: "semantic_query", "metric_query", "data_question", "chitchat", hoặc "out_of_scope"

Câu hỏi trước đây:
{history}

Latest request: {user_message}"""

_INTENTS = {"chitchat", "semantic_query", "data_question", "metric_query", "out_of_scope"}


async def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """Classify user message into chitchat, semantic_query, data_question, metric_query, or out_of_scope.

    Uses LLM with temperature=0.0 for deterministic classification.
    Falls back to 'chitchat' on error to avoid breaking the conversation.
    """
    existing_intent = state.get("intent")
    if existing_intent in _INTENTS:
        return {"intent": existing_intent}
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"intent": "chitchat", "chat_response": "Bạn chưa nhập câu hỏi. Tôi có thể giúp gì?"}
    try:
        response = await get_llm().ainvoke(_classification_prompt(state, user_message))
        raw = (response.content if hasattr(response, "content") else str(response)).strip().lower()
        intent = _parse_intent(raw)
        logger.info(
            "Orchestrator classified message (len=%d) → intent=%s",
            len(user_message),
            intent,
        )
        if intent == "out_of_scope":
            return {"intent": "out_of_scope", "chat_response": _OUT_OF_SCOPE_RESPONSE}
        return {"intent": intent}
    except Exception as exc:
        logger.warning("Orchestrator failed; defaulting to metric query: %s", exc)
        return {"intent": "metric_query"}


def _classification_prompt(state: AgentState, user_message: str) -> str:
    """Build a bounded classification prompt from the recent chat history."""
    history = _format_history(state.get("chat_history", []))
    return _CLASSIFY_PROMPT.format(history=history, user_message=user_message)


def _parse_intent(raw: str) -> str:
    """Parse raw LLM response into recognized intent string."""
    if "semantic_query" in raw:
        return "semantic_query"
    if "metric_query" in raw:
        return "metric_query"
    if "data_question" in raw:
        return "data_question"
    if "out_of_scope" in raw or "unrelated" in raw:
        return "out_of_scope"
    if "chitchat" in raw:
        return "chitchat"
    return "data_question"


def _format_history(history: list[dict[str, str]]) -> str:
    """Format a small untrusted history excerpt for intent classification."""
    lines = []
    for item in history[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()[:1000]
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"
