"""Parse natural-language questions into structured SemanticQueryInterpretation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.agents.state import AgentState
from src.models.schemas import (
    ChatClarificationOption,
    ChatClarificationPayload,
    DimensionSelection,
    SemanticQueryFilter,
    SemanticQueryInterpretation,
    SemanticQuerySpec,
    SemanticTimeRange,
)
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json

logger = logging.getLogger(__name__)

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_PARSE_PROMPT = """Bạn là chuyên gia Semantic Query Parser của hệ thống AI Semantic Layer.
Nhiệm vụ: Chuyển đổi câu hỏi tiếng Việt của người dùng thành cấu trúc truy vấn Semantic Query hoặc yêu cầu làm rõ (Clarification) nếu mơ hồ.

Thời gian hiện tại tại Việt Nam (Asia/Ho_Chi_Minh): {current_time}

CATALOG CHỈ SỐ VÀ CHIỀU ĐÃ ĐƯỢC PHÊ DUYỆT:
{catalog_json}

Lịch sử hội thoại:
{history}

Câu hỏi người dùng: "{user_message}"

QUY TẮC BẮT BUỘC:
1. CHỈ ĐƯỢC DÙNG metric_id và column_id có trong CATALOG ở trên. TUYỆT ĐỐI KHÔNG TỰ NGHĨ RA ID.
2. ĐỘ PHÙ HỢP NGHIỆP VỤ (QUAN TRỌNG NHẤT):
   - CHỈ CHỌN metric_id nếu ý nghĩa nghiệp vụ (name, business_name), công thức và filters có sẵn thực sự khớp với câu hỏi của người dùng.
   - TUYỆT ĐỐI KHÔNG gượng ép chọn metric có ý nghĩa trái ngược hoặc khác biệt (ví dụ: người dùng hỏi "đơn hàng hoàn thành" / "thành công" mà trong catalog chỉ có metric "Tỷ lệ hủy đơn hàng" có filter is_canceled=1, thì TUYỆT ĐỐI KHÔNG CHỌN metric này).
   - Nếu KHÔNG CÓ metric nào trong catalog phù hợp với câu hỏi của người dùng: BẮT BUỘC trả về status: "needs_clarification" với clarification.prompt giải thích rõ ràng metric chưa có và gợi ý các metric hiện có hoặc hướng dẫn tạo metric mới.
3. Nếu câu hỏi rõ ràng và map được metric/dimension/filter hợp lệ:
   - status: "resolved"
   - metric_ids: danh sách ID chỉ số đã chọn (ví dụ [1])
   - dimensions: danh sách {{"column_id": int, "time_grain": "day"|"week"|"month"|"quarter"|"year"|null}}
   - filters: danh sách {{"column_id": int, "operator": "eq"|"neq"|"gt"|"gte"|"lt"|"lte"|"in"|"not_in"|"is_null"|"is_not_null", "value": any}}
   - time_ranges: danh sách {{"column_id": int, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "label": "Năm 2024"}} (khoảng thời gian nửa mở [start_date, end_date))
   - limit: số dòng tối đa (mặc định 100, tối đa 1000)
4. Nếu câu hỏi mơ hồ, thiếu thông tin hoặc chưa có metric phù hợp trong catalog:
   - status: "needs_clarification"
   - clarification: {{"prompt": "Câu hỏi làm rõ tiếng Việt", "options": [
       {{"id": "opt_1", "label": "Nhãn hiển thị ngắn", "description": "Mô tả chi tiết", "spec": {{"metric_ids": [...], "dimensions": [...], "filters": [], "limit": 100}}}}
     ]}} (tối đa 3 options có spec hoàn chỉnh từ các metric sẵn có).
5. rationale: Giải thích ngắn gọn lý do chọn metric/dimension hoặc lý do cần làm rõ.

CHỈ TRẢ VỀ DUY NHẤT 1 JSON OBJECT hợp lệ theo cấu trúc sau:
{{
  "status": "resolved" | "needs_clarification",
  "metric_ids": [1],
  "dimensions": [{{"column_id": 2, "time_grain": null}}],
  "filters": [],
  "time_ranges": [],
  "limit": 100,
  "clarification": null,
  "rationale": "..."
}}"""


async def semantic_parse_node(state: AgentState) -> dict[str, Any]:
    """Parse user query against catalog using LLM without direct DB execution."""
    catalog = state.get("parser_catalog") or {}
    metrics = catalog.get("metrics") or []
    if not metrics:
        return _empty_catalog_fallback()

    user_message = state.get("user_message", "").strip()
    prompt = _build_parse_prompt(state, user_message, catalog)
    try:
        raw_json = await ainvoke_json(get_llm(), prompt, retries=1)
        interpretation = _parse_interpretation(raw_json, catalog)
    except Exception as exc:
        logger.warning("Semantic parse node failed: %s", exc)
        interpretation = _fallback_interpretation(
            "Tôi chưa hiểu rõ câu hỏi số liệu của bạn. Bạn có thể diễn đạt cụ thể hơn không?"
        )

    return _build_node_output(interpretation)


def _empty_catalog_fallback() -> dict[str, Any]:
    """Return polite clarification when no approved metrics exist."""
    msg = "Chưa có Business Metric nào được phê duyệt để truy vấn. Bạn vui lòng duyệt metric trước."
    interp = SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=msg, options=[]),
    )
    return {"intent": "semantic_query", "interpretation": interp.model_dump(), "chat_response": msg}


def _build_parse_prompt(state: AgentState, user_message: str, catalog: dict[str, Any]) -> str:
    """Format catalog, history, and current Vietnam time into the prompt."""
    now_vn = datetime.now(_VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    history_str = _format_history(state.get("chat_history", []))
    compact_catalog = json.dumps(catalog, ensure_ascii=False, indent=2)
    return _PARSE_PROMPT.format(
        current_time=now_vn,
        catalog_json=compact_catalog,
        history=history_str,
        user_message=user_message,
    )


def _format_history(history: list[dict[str, str]]) -> str:
    """Format recent history into readable lines."""
    lines = []
    for item in history[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()[:500]
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"


def _parse_interpretation(raw: dict[str, Any], catalog: dict[str, Any]) -> SemanticQueryInterpretation:
    """Convert raw LLM dict into validated SemanticQueryInterpretation."""
    status = raw.get("status")
    if status == "resolved":
        spec = _build_spec(raw, catalog)
        if spec is not None:
            time_ranges = _build_time_ranges(raw.get("time_ranges", []))
            return SemanticQueryInterpretation(
                status="resolved",
                spec=spec,
                time_ranges=time_ranges,
                rationale=raw.get("rationale"),
            )
    return _build_clarification_interpretation(raw)


def _build_spec(raw: dict[str, Any], catalog: dict[str, Any]) -> SemanticQuerySpec | None:
    """Construct SemanticQuerySpec from raw output after verifying IDs."""
    metric_ids = [int(m) for m in raw.get("metric_ids", []) if isinstance(m, (int, str)) and str(m).isdigit()]
    if not metric_ids:
        return None

    valid_metric_ids = {m["id"] for m in catalog.get("metrics", [])}
    if not set(metric_ids).issubset(valid_metric_ids):
        return None

    dims = [DimensionSelection(**d) for d in raw.get("dimensions", []) if isinstance(d, dict) and "column_id" in d]
    filters = [SemanticQueryFilter(**f) for f in raw.get("filters", []) if isinstance(f, dict) and "column_id" in f]
    limit = min(max(int(raw.get("limit", 100)), 1), 1000)

    return SemanticQuerySpec(metric_ids=metric_ids, dimensions=dims, filters=filters, limit=limit)


def _build_time_ranges(items: list[Any]) -> list[SemanticTimeRange]:
    """Parse time ranges safely."""
    ranges: list[SemanticTimeRange] = []
    for item in items:
        if isinstance(item, dict) and "column_id" in item and "start_date" in item and "end_date" in item:
            ranges.append(
                SemanticTimeRange(
                    column_id=item["column_id"],
                    start_date=str(item["start_date"]),
                    end_date=str(item["end_date"]),
                    label=str(item.get("label", "")),
                )
            )
    return ranges


def _build_clarification_interpretation(raw: dict[str, Any]) -> SemanticQueryInterpretation:
    """Build a needs_clarification interpretation from clarification payload."""
    clar_data = raw.get("clarification")
    prompt = "Tôi cần thêm thông tin để chạy truy vấn chính xác. Bạn vui lòng chọn một trong các gợi ý dưới đây:"
    options: list[ChatClarificationOption] = []
    if isinstance(clar_data, dict):
        prompt = clar_data.get("prompt") or prompt
        for opt in clar_data.get("options", []):
            if isinstance(opt, dict) and "id" in opt and "label" in opt and "spec" in opt:
                try:
                    options.append(
                        ChatClarificationOption(
                            id=str(opt["id"]),
                            label=str(opt["label"]),
                            description=opt.get("description"),
                            spec=SemanticQuerySpec(**opt["spec"]),
                        )
                    )
                except Exception as exc:
                    logger.debug("Skipping invalid clarification option: %s", exc)
                    continue
    return SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=prompt, options=options[:3]),
        rationale=raw.get("rationale"),
    )


def _fallback_interpretation(msg: str) -> SemanticQueryInterpretation:
    """Generate fallback interpretation on parse error."""
    return SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=msg, options=[]),
    )


def _build_node_output(interpretation: SemanticQueryInterpretation) -> dict[str, Any]:
    """Format state update for LangGraph."""
    out: dict[str, Any] = {
        "intent": "semantic_query",
        "interpretation": interpretation.model_dump(),
    }
    if interpretation.status == "needs_clarification":
        prompt = interpretation.clarification.prompt if interpretation.clarification else "Vui lòng làm rõ câu hỏi."
        out["chat_response"] = prompt
        out["clarification"] = interpretation.clarification.model_dump() if interpretation.clarification else None
    return out
