"""Classify chat requests for direct data guidance or metric generation."""

from __future__ import annotations

import logging
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_OUT_OF_SCOPE_RESPONSE = (
    "Tôi là trợ lý AI chuyên về Semantic Layer và phân tích dữ liệu doanh nghiệp. "
    "Câu hỏi hoặc yêu cầu của bạn hiện không thuộc phạm vi hỗ trợ của hệ thống. "
    "Tôi chỉ hỗ trợ các câu hỏi liên quan đến cơ sở dữ liệu, schema, bảng, cột, "
    "Business Metrics và tính năng của hệ thống Semantic Layer. "
    "Bạn có câu hỏi nào về dữ liệu cần tôi hỗ trợ không?"
)

_CLASSIFIER_ERROR_RESPONSE = (
    "Xin lỗi, tôi đang gặp sự cố tạm thời khi xử lý yêu cầu của bạn. "
    "Bạn có thể thử lại hoặc đặt câu hỏi về dữ liệu, Business Metrics, "
    "schema cơ sở dữ liệu để tôi hỗ trợ không?"
)

_CLASSIFY_PROMPT = """Bạn là bộ phân loại câu hỏi thông minh cho hệ thống AI Semantic Layer.
Phân loại câu hỏi của người dùng vào đúng 1 trong 5 nhóm:

- "semantic_query": Câu hỏi yêu cầu xem số liệu, kết quả, báo cáo, truy vấn, thống kê, tính toán dữ liệu HOẶC yêu cầu tính toán chỉ số (ví dụ: "tôi muốn tính tỷ lệ hủy đơn", "tính biên lợi nhuận gộp", "tính giá trị đơn hàng trung bình aov", "tính tỷ lệ khách bỏ giỏ hàng không mua", "tính thời gian giao hàng trung bình", "tính doanh thu theo vùng", "Tạo metric tính doanh thu theo vùng"). MỌI CÂU HỎI BẮT ĐẦU BẰNG "TÍNH...", "TÔI MUỐN TÍNH..." ĐỀU THUỘC NHÓM NÀY ĐỂ ĐƯỢC LÀM RÕ (CLARIFY) VÀ TẠO CHỈ SỐ.
- "metric_query": Yêu cầu tạo mới, chỉnh sửa, xây dựng hoặc đề xuất công thức định nghĩa Business Metric hoàn toàn mới vào hệ thống (ví dụ: "Tạo metric mới Doanh thu thuần", "Đề xuất metric cho bảng orders", "Định nghĩa công thức AOV", "Tạo chỉ số tỷ lệ hủy đơn").
- "data_question": Hỏi về cấu trúc database, schema, bảng, cột, kiểu dữ liệu, glossary, quan hệ bảng (ví dụ: "Bảng customer có những cột nào?", "Khóa ngoại giữa orders và users là gì?"). TUYỆT ĐỐI KHÔNG phân loại các yêu cầu tính toán chỉ số vào nhóm này.
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
        if existing_intent == "out_of_scope":
            return {
                "intent": "out_of_scope",
                "chat_response": state.get("chat_response") or _OUT_OF_SCOPE_RESPONSE,
            }
        return {"intent": existing_intent}
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"intent": "chitchat", "chat_response": "Bạn chưa nhập câu hỏi. Tôi có thể giúp gì?"}
    try:
        response = await get_llm().ainvoke(_classification_prompt(state, user_message))
        raw = (response.content if hasattr(response, "content") else str(response)).strip().lower()
        intent = _parse_intent(raw, user_message)
        logger.info(
            "Orchestrator classified message (len=%d) → intent=%s",
            len(user_message),
            intent,
        )
        if intent == "out_of_scope":
            return {"intent": "out_of_scope", "chat_response": _OUT_OF_SCOPE_RESPONSE}
        return {"intent": intent}
    except Exception as exc:
        logger.warning("Orchestrator failed; falling back to safe non-mutating chitchat: %s", exc)
        return {"intent": "chitchat", "chat_response": _CLASSIFIER_ERROR_RESPONSE}


def _classification_prompt(state: AgentState, user_message: str) -> str:
    """Build a bounded classification prompt from the recent chat history."""
    history = _format_history(state.get("chat_history", []))
    return _CLASSIFY_PROMPT.format(history=history, user_message=user_message)


def _parse_intent(raw: str, user_message: str = "") -> str:
    """Parse raw LLM response into recognized intent string."""
    cleaned = raw.strip().lower()
    if "metric_query" in cleaned:
        return "metric_query"
    if "semantic_query" in cleaned:
        return "semantic_query"
    if "data_question" in cleaned:
        return "data_question"
    if "out_of_scope" in cleaned or "unrelated" in cleaned:
        return "out_of_scope"
    if "chitchat" in cleaned:
        return "chitchat"
    lowered = user_message.lower().strip()
    if lowered.startswith(("tính ", "tôi muốn tính ", "tạo metric", "tạo chỉ số")):
        return "semantic_query"
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
