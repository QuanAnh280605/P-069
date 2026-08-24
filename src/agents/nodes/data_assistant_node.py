"""Read-only data guidance node for Workspace members and Data Leads."""

from __future__ import annotations

import json
import logging
import unicodedata
from typing import Any

from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

_MISSING_INPUT_LABELS = {
    "transaction_table": "Bảng giao dịch (ví dụ: `order`, `sale` hoặc `transaction`) liên kết với khách hàng.",
    "customer_link_column": "Cột liên kết giao dịch với khách hàng (ví dụ: `customer_id`).",
    "status_column": "Cột trạng thái giao dịch, nếu KPI chỉ tính giao dịch hoàn tất.",
    "source_table": "Bảng nguồn chứa bản ghi dùng để tính metric.",
    "metric_column": "Cột dữ liệu cần dùng cho công thức metric.",
    "relationship": "Quan hệ khóa giữa các bảng cần dùng để tính metric.",
    "grain": "Khóa định danh hoặc grain xác định mỗi bản ghi được đếm một lần.",
}

_SYSTEM_PROMPT = """Bạn là Data Assistant của AI Semantic Layer Agent.
Chỉ hỗ trợ người dùng hiểu schema, glossary, quan hệ bảng, metric đã được phê duyệt,
và cách chọn Metric/Dimension/Filter để truy vấn an toàn.

Không được tạo, sửa hoặc phê duyệt metric. Không viết SQL tự do, không đoán dữ liệu
không có trong context, không tiết lộ connection string hay thông tin bí mật.
Hãy tuân thủ Metric Decision đã được server xác thực. Nếu decision là approved_metric_match,
giải thích metric approved đã match và cách dùng definition đó. Không nói người dùng không có quyền
tạo metric; quyền thao tác được UI xử lý sau khi một proposal hợp lệ đã được sinh.
MỌI câu trả lời hiển thị cho người dùng PHẢI hoàn toàn bằng tiếng Việt; chỉ giữ nguyên tên bảng/cột,
metric hoặc mã kỹ thuật có trong context. Luôn dùng Markdown sáng sủa: mỗi ý chính xuống dòng,
dùng danh sách đánh số/gạch đầu dòng, code inline cho tên bảng/cột, và nếu dùng bảng thì phải là
GFM table hợp lệ có dòng trống trước và sau. Không nối nhiều ý vào một đoạn dài."""

_MAX_HISTORY_CHARS = 10000


async def data_assistant_node(state: AgentState) -> dict[str, Any]:
    """Answer read-only schema and approved-metric questions."""
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"intent": "data_question", "chat_response": "Bạn muốn tìm hiểu phần dữ liệu nào?"}
    metric_list_response = _approved_metric_list_response(user_message, state.get("approved_metrics", []))
    if metric_list_response:
        return {"intent": "data_question", "chat_response": metric_list_response}
    direct_response = _direct_decision_response(state)
    if direct_response:
        return {"intent": "data_question", "chat_response": direct_response}
    context = _format_context(state)
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


def _approved_metric_list_response(user_message: str, metrics: Any) -> str | None:
    """List approved metrics deterministically when the user asks for the catalog."""
    if not _asks_for_metric_catalog(user_message):
        return None
    names = [item.get("name") for item in metrics if isinstance(item, dict) and item.get("name")]
    if not names:
        return "Hiện Semantic Layer chưa có metric nào đã được phê duyệt."
    items = "\n".join(f"- **{name}**" for name in names)
    return f"Hiện Semantic Layer có {len(names)} metric đã được phê duyệt:\n\n{items}"


def _asks_for_metric_catalog(user_message: str) -> bool:
    """Recognize a request to list the approved metric catalog."""
    normalized = _without_accents(user_message).lower()
    markers = ("co nhung", "danh sach", "liet ke", "bao nhieu", "metric gi")
    return "metric" in normalized and any(marker in normalized for marker in markers)


def _without_accents(value: str) -> str:
    """Normalize Vietnamese text for lightweight intent matching."""
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _direct_decision_response(state: AgentState) -> str | None:
    """Return deterministic safe guidance for unsupported or failed decisions."""
    decision = state.get("metric_decision", {})
    if state.get("error"):
        return "Không thể tạo Metric Definition hợp lệ từ schema hiện tại. Vui lòng thử lại sau."
    if decision.get("fallback"):
        return "Không thể xác định metric chắc chắn lúc này. Vui lòng diễn đạt rõ KPI hoặc thử lại sau."
    if decision.get("kind") != "missing_metric_unsupported":
        return None
    items = _missing_input_items(decision.get("missing_input_codes", []))
    return (
        "Chưa thể tạo Metric Definition hợp lệ vì schema hiện tại chưa đủ dữ liệu để xác định KPI an toàn."
        f"\n\nCần bổ sung:\n{items}"
    )


def _missing_input_items(codes: Any) -> str:
    """Render schema-gap codes with server-owned Vietnamese labels only."""
    if not isinstance(codes, list):
        return "- Bảng, cột hoặc quan hệ cần thiết để định nghĩa metric."
    labels = [_MISSING_INPUT_LABELS[code] for code in codes if code in _MISSING_INPUT_LABELS]
    return "\n".join(f"- {label}" for label in labels) or "- Bảng, cột hoặc quan hệ cần thiết để định nghĩa metric."


def _format_context(state: AgentState) -> str:
    """Serialize bounded semantic context and its verified metric decision."""
    metrics = state.get("approved_metrics", [])
    decision = state.get("metric_decision", {})
    matched_id = decision.get("matched_metric_id")
    matched = next(
        (item for item in metrics if isinstance(item, dict) and item.get("id") == matched_id),
        None,
    )
    payload = {
        "schema": state.get("enriched_schema", {}),
        "approved_metrics": metrics,
        "metric_decision": decision,
        "matched_metric": matched,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)
