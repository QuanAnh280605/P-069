"""Parse natural-language questions into structured SemanticQueryInterpretation."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

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

_PARSE_PROMPT = """Bạn là trợ lý AI chuyên gia phân tích dữ liệu và Semantic Query của hệ thống AI Semantic Layer.
Nhiệm vụ: Phân tích câu hỏi/yêu cầu của người dùng, xác định đúng Ý ĐỊNH (Intent) và trả về JSON cấu trúc chuẩn xác.

Thời gian hiện tại tại Việt Nam (Asia/Ho_Chi_Minh): {current_time}
Vai trò người dùng: {role_description}

DANH MỤC CHỈ SỐ VÀ CHIỀU ĐÃ ĐƯỢC PHÊ DUYỆT (CATALOG):
{catalog_json}

CẤU TRÚC SEMANTIC LAYER (CÁC BẢNG VÀ CHIỀU CÓ THỂ KẾT NỐI VỚI CHỈ SỐ):
{semantic_schema_text}

Lịch sử hội thoại:
{history}

Câu hỏi người dùng: "{user_message}"

QUY TẮC PHÂN LOẠI VÀ XỬ LÝ:

1. Ý ĐỊNH CHÀO HỎI / GIAO TIẾP CHUNG ("intent": "chitchat"):
   - Khi người dùng chào hỏi, cảm ơn, tạm biệt, hỏi tính năng hệ thống HOẶC báo cáo/phản hồi lỗi hệ thống (ví dụ: "tôi cần báo cáo lỗi hệ thống").
   - Trả về: {{"intent": "chitchat", "chat_response": "<câu trả lời tự nhiên, lịch sự bằng tiếng Việt>"}}

2. Ý ĐỊNH NGOÀI PHẠM VI ("intent": "out_of_scope"):
   - Khi câu hỏi KHÔNG liên quan đến dữ liệu doanh nghiệp hay tính năng hệ thống (thời tiết, nấu ăn, giải trí...).
   - Trả về: {{"intent": "out_of_scope", "chat_response": "<câu từ chối lịch sự và hướng dẫn quay lại chủ đề dữ liệu>"}}

3. Ý ĐỊNH TẠO / ĐỀ XUẤT METRIC MỚI ("intent": "metric_query"):
   - Khi người dùng muốn định nghĩa công thức chỉ số mới CHƯA CÓ TRONG CATALOG và KHÔNG CÓ chiều phân nhóm mơ hồ (ví dụ: "định nghĩa công thức AOV", "tạo metric Doanh thu thuần").
   - LƯU Ý BẮT BUỘC: Nếu chỉ số đó ĐÃ CÓ trong CATALOG (ví dụ: "Doanh thu" đã có) hoặc yêu cầu chứa khái niệm phân nhóm (ví dụ: "theo vùng", "theo khu vực", "tính doanh thu theo vùng", "tạo metric tính doanh thu theo vùng"): BẮT BUỘC chọn "intent": "semantic_query" và áp dụng Quy tắc 4.B để LÀM RÕ (CLARIFY) chiều phân tích với người dùng trước! KHÔNG ĐƯỢC sinh metric khi chưa làm rõ.

4. Ý ĐỊNH TRUY VẤN DỮ LIỆU THỰC TẾ ("intent": "semantic_query"):
   - A. Nếu câu hỏi có chỉ số rõ ràng và chiều phân tích khớp trực tiếp:
     status: "resolved", metric_ids: [<id>], dimensions: [{{"column_id": <id>, "time_grain": null}}], filters: [], time_ranges: [], limit: 100, rationale: "..."
   - B. Nếu câu hỏi yêu cầu phân nhóm (ví dụ: "theo vùng", "theo kênh", "theo đối tượng", "theo thanh toán", "tính doanh thu theo vùng", "tạo metric tính doanh thu theo vùng"...):
     ĐỌC CẤU TRÚC SEMANTIC LAYER Ở TRÊN ĐỂ SUY LUẬN NGỮ NGHĨA (KHÔNG DÙNG TỪ ĐIỂN CỨNG):
     + Nếu khái niệm đó có thể liên quan đến một hoặc nhiều chiều trong Semantic Layer (ví dụ: "theo vùng" có thể liên quan đến Khu vực, Thành phố, Cửa hàng...; "theo thanh toán" liên quan đến Phương thức thanh toán...):
       status: "needs_clarification",
       clarification: {{
         "prompt": "Bạn muốn xem <Tên chỉ số> theo góc nhìn nào của '<khái niệm>'? Dữ liệu có các chiều sau:",
         "options": [
           {{
             "id": "opt_1",
             "label": "Theo <Tên chiều> (bảng <Tên bảng>)",
             "description": "<Mô tả ngắn gọn>",
             "spec": {{
               "metric_ids": [<id của chỉ số được hỏi>],
               "dimensions": [{{"column_id": <column_id tương ứng trong schema>, "time_grain": null}}],
               "filters": [],
               "limit": 100
             }}
           }}
         ]
       }}
       (Tối đa 3 options phù hợp nhất từ Semantic Layer)
     + Nếu khái niệm khớp rõ ràng với duy nhất 1 chiều:
       status: "resolved", metric_ids: [<id>], dimensions: [{{"column_id": <id>, "time_grain": null}}], filters: [], time_ranges: [], limit: 100, rationale: "..."
     + Nếu khái niệm HOÀN TOÀN KHÔNG CÓ trong Semantic Layer:
       status: "needs_clarification", clarification: {{"prompt": "Dữ liệu hiện không có thông tin về '<khái niệm>'. Bạn có thể chọn các chiều có sẵn dưới đây:", "options": []}}
   - C. Nếu chỉ số hỏi CHƯA CÓ trong CATALOG:
     status: "needs_clarification", clarification.prompt: "Hệ thống hiện chưa có chỉ số '<Tên chỉ số>'. Bạn có muốn {action_prompt} này không?",
     clarification.options: [{{"id": "create_metric", "label": "{action_label} '<Tên chỉ số>'", "spec": null, "action": "create_metric"}}]

CHỈ TRẢ VỀ DUY NHẤT 1 JSON OBJECT hợp lệ theo một trong các mẫu trên."""


_CREATE_INDICATORS = frozenset(
    {
        "tạo metric",
        "tao metric",
        "thêm metric",
        "them metric",
        "đề xuất metric",
        "de xuat metric",
        "định nghĩa",
        "dinh nghia",
        "tạo chỉ số",
        "tao chi so",
        "tính metric",
        "tính toán",
        "tính ",
        "tinh ",
        "tôi muốn tính",
        "tỷ lệ",
        "ty le",
        "biên lợi nhuận",
        "gross margin",
        "aov",
        "giá trị đơn",
        "hoàn trả",
        "thâm nhập",
    }
)


def _is_metric_creation_intent(user_message: str, pre_intent: str) -> bool:
    """Check if the user is asking to create, define, or calculate a business metric."""
    if pre_intent == "metric_query":
        return True
    lowered = user_message.lower().strip()
    if lowered.startswith(("xem ", "cho tôi xem ", "tra cứu ", "hiển thị ")):
        return False
    return any(kw in lowered for kw in _CREATE_INDICATORS)


def _is_clarified(state: AgentState, user_message: str) -> bool:
    """Detect if the current turn represents an answered clarification."""
    if state.get("is_clarified"):
        return True
    if state.get("clarification_selection"):
        return True
    if user_message.startswith("Tạo metric dựa trên lựa chọn đã làm rõ") or user_message.startswith(
        "Tạo định nghĩa metric:"
    ):
        return True
    history = state.get("chat_history") or []
    if history:
        last_item = history[-1]
        if last_item.get("role") == "assistant" and "làm rõ" in last_item.get("content", "").lower():
            return True
    return False


def _has_explicit_dimension_intent(user_message: str) -> bool:
    """Check if the user explicitly requested grouping by dimensions."""
    lowered = f" {user_message.lower().strip()} "
    indicators = [
        " theo ",
        " từng ",
        " chia theo ",
        " phân theo ",
        " phân loại theo ",
        " theo kênh",
        " theo khu vực",
        " theo vùng",
        " theo ngày",
        " theo tháng",
        " theo năm",
        " theo quý",
        " theo trạng thái",
        " theo khách hàng",
        " theo cửa hàng",
    ]
    return any(ind in lowered for ind in indicators)


def _clean_metric_name_target(user_message: str) -> str:
    """Extract clean target metric name from user message."""
    clean = re.sub(
        r"^(tạo\s+metric\s+|tạo\s+chỉ\s+số\s+|định\s+nghĩa\s+chỉ\s+số\s+|định\s+nghĩa\s+|tính\s+toán\s+|tính\s+cho\s+tôi\s+|tôi\s+muốn\s+tính\s+|tính\s+)",
        "",
        user_message,
        flags=re.IGNORECASE,
    ).strip()
    return clean or user_message.strip()


def _format_candidate_dims_text(candidate_dims: list[dict[str, Any]]) -> str:
    """Format candidate dimensions into text bullet points."""
    dim_items = []
    for c in candidate_dims[:10]:
        c_name = c.get("column_name") or ""
        b_name = c.get("business_name") or c_name
        t_name = c.get("table_business_name") or c.get("table_name") or ""
        dim_items.append(f"- {b_name} (cột `{c_name}` bảng {t_name})")
    return "\n".join(dim_items) if dim_items else "(Chưa có danh sách chiều mở rộng)"


def _metric_clarify_guidance_and_samples(has_dim_req: bool, clean_name: str) -> tuple[str, str, str, str]:
    """Provide LLM prompt instructions and sample JSON options."""
    if has_dim_req:
        guidance = (
            "2. Đề xuất các chiều phân tích (dimensions) phù hợp với yêu cầu phân nhóm của người dùng "
            "(ví dụ: khu vực, kênh bán, thời gian...)."
        )
        sample1 = '{"id": "opt_1", "label": "Chỉ tính đơn hợp lệ · Theo Kênh bán", "description": "Loại đơn hủy/test, phân tích theo kênh", "dimensions": ["cột_dim_1"]}'
        sample2 = '{"id": "opt_2", "label": "Tính trên toàn bộ đơn hàng · Theo Khu vực", "description": "Tính trên toàn bộ bản ghi, phân tích theo khu vực", "dimensions": ["cột_dim_2"]}'
        intro = f"Để tạo chỉ số '{clean_name}' chuẩn xác theo chiều phân tích mong muốn, bạn vui lòng chọn phương án tính toán và chiều phân tích dưới đây:"
        return guidance, sample1, sample2, intro

    guidance = (
        "2. Chiều phân tích là TÙY CHỌN (OPTIONAL): Người dùng KHÔNG yêu cầu phân nhóm theo chiều cụ thể trong câu hỏi. "
        "Các phương án chỉ tập trung làm rõ logic tính toán và điều kiện lọc (ví dụ: loại trừ đơn hủy/test vs tính toàn bộ đơn). "
        "TUYỆT ĐỐI KHÔNG thêm cụm từ '· Gắn chiều ...' vào nhãn (label) của các phương án."
    )
    sample1 = '{"id": "opt_1", "label": "Chỉ tính đơn hợp lệ (loại trừ đơn hủy/thử nghiệm)", "description": "Loại trừ đơn thử nghiệm và đơn đã hủy khỏi phép tính", "dimensions": []}'
    sample2 = '{"id": "opt_2", "label": "Tính trên toàn bộ đơn hàng", "description": "Tính toán trên toàn bộ bản ghi", "dimensions": []}'
    intro = (
        f"Để tạo chỉ số '{clean_name}' chuẩn xác và không bị nhầm lẫn, bạn vui lòng chọn phương án tính toán dưới đây:"
    )
    return guidance, sample1, sample2, intro


def _build_metric_clarify_prompt(
    clean_name: str,
    user_message: str,
    semantic_schema_text: str,
    dims_text: str,
    has_dim_req: bool,
) -> str:
    """Format clarify prompt for LLM, treating dimensions as optional unless requested."""
    guidance, opt1, opt2, intro = _metric_clarify_guidance_and_samples(has_dim_req, clean_name)
    rules_text = (
        "Nhiệm vụ: Bạn PHẢI làm rõ (clarify) với người dùng:\n"
        "1. Logic tính toán và điều kiện lọc (ví dụ: loại trừ đơn hủy/đơn test, cách tính tỷ lệ hay tổng...).\n"
        f"{guidance}\n"
        "3. Khi tính tỷ lệ (như tỷ lệ hủy, hoàn trả) trên cột cờ hiệu chữ/boolean: KHÔNG dùng AVG mà đề xuất COUNT kèm bộ lọc.\n"
        "4. Nếu tính chỉ số phức tạp (như khách quay lại, retention) mà schema thiếu bảng mua lặp lại: hãy giải thích trong prompt và đề xuất phương án khả thi từ dữ liệu (ví dụ: Tổng khách hàng đặt đơn).\n"
        "5. Lưu ý kỹ thuật: Hàm AVG/SUM chỉ áp dụng cho cột kiểu số. Không đề xuất trừ hai cột thời gian/ngày tháng."
    )
    return (
        f"Bạn là chuyên gia dữ liệu AI Semantic Layer.\n"
        f'Người dùng (non-tech) muốn tạo hoặc tính toán chỉ số: "{user_message}".\n\n'
        f"{rules_text}\n\n"
        f"Cấu trúc Schema khả dụng:\n{semantic_schema_text[:1200]}\n\n"
        f"Các chiều phân tích khả dụng:\n{dims_text}\n\n"
        f'Trả về DUY NHẤT 1 JSON theo cấu trúc:\n{{\n  "prompt": "{intro}",\n  "options": [\n    {opt1},\n    {opt2}\n  ]\n}}'
    )


def _parse_metric_clarify_json(
    raw_json: Any,
    default_prompt: str,
) -> tuple[str, list[ChatClarificationOption]]:
    """Parse JSON from LLM into prompt text and options."""
    if not isinstance(raw_json, dict) or not raw_json.get("options"):
        return default_prompt, []
    prompt_text = str(raw_json.get("prompt") or default_prompt)
    options: list[ChatClarificationOption] = []
    for i, opt in enumerate(raw_json["options"]):
        opt_id = str(opt.get("id") or f"opt_{i + 1}")
        label = str(opt.get("label") or f"Phương án {i + 1}")
        dimensions = [str(item) for item in opt.get("dimensions", []) if item]
        options.append(
            ChatClarificationOption(
                id=opt_id,
                label=label,
                description=opt.get("description"),
                dimensions=dimensions,
                action="create_metric",
                spec=None,
            )
        )
    return prompt_text, options


def _fallback_concept_options(clean_name: str) -> list[ChatClarificationOption] | None:
    """Return specialized fallback options for tricky business concepts."""
    lowered = clean_name.lower()
    if any(k in lowered for k in ["quay lại", "retention", "mua lại", "lặp lại"]):
        return [
            ChatClarificationOption(
                id="opt_1",
                label=f"Tổng số khách hàng từng đặt đơn cho '{clean_name}'",
                description="Đếm số lượng khách hàng duy nhất (COUNT_DISTINCT customer_id)",
                dimensions=[],
                action="create_metric",
            ),
            ChatClarificationOption(
                id="opt_2",
                label=f"Tổng số đơn hàng phát sinh cho '{clean_name}'",
                description="Đếm toàn bộ đơn hàng hợp lệ đã phát sinh trong hệ thống",
                dimensions=[],
                action="create_metric",
            ),
        ]
    return None


def _fallback_logic_only_options(clean_name: str) -> list[ChatClarificationOption]:
    """Return fallback options focusing only on calculation logic."""
    return [
        ChatClarificationOption(
            id="opt_1",
            label=f"Chỉ tính đơn hợp lệ (loại đơn hủy/test) cho '{clean_name}'",
            description=f"Áp dụng bộ lọc loại trừ đơn thử nghiệm/hủy khi tính metric '{clean_name}'.",
            dimensions=[],
            action="create_metric",
        ),
        ChatClarificationOption(
            id="opt_2",
            label=f"Tính trên toàn bộ đơn hàng cho '{clean_name}'",
            description=f"Tính toán trên toàn bộ bản ghi cho metric '{clean_name}'.",
            dimensions=[],
            action="create_metric",
        ),
        ChatClarificationOption(
            id="opt_3",
            label=f"Chỉ tính đơn giao dịch thành công cho '{clean_name}'",
            description=f"Chỉ tính các đơn giao dịch thành công cho metric '{clean_name}'.",
            dimensions=[],
            action="create_metric",
        ),
    ]


def _fallback_dimension_options(clean_name: str, candidate_dims: list[dict[str, Any]]) -> list[ChatClarificationOption]:
    """Return fallback options with candidate dimension groupings."""
    d1 = candidate_dims[0].get("column_name", "channel") if candidate_dims else "channel"
    d1_label = candidate_dims[0].get("business_name", "Kênh bán") if candidate_dims else "Kênh bán"
    d2 = candidate_dims[1].get("column_name", "city_name") if len(candidate_dims) > 1 else "city_name"
    d2_label = candidate_dims[1].get("business_name", "Khu vực") if len(candidate_dims) > 1 else "Khu vực"
    return [
        ChatClarificationOption(
            id="opt_1",
            label=f"Chỉ tính đơn hợp lệ (loại đơn hủy/test) · Theo {d1_label}",
            description=f"Áp dụng bộ lọc loại trừ đơn thử nghiệm/hủy và phân tích theo {d1_label}.",
            dimensions=[d1],
            action="create_metric",
        ),
        ChatClarificationOption(
            id="opt_2",
            label=f"Tính trên toàn bộ đơn hàng · Theo {d2_label}",
            description=f"Tính toán trên toàn bộ bản ghi và phân tích theo {d2_label}.",
            dimensions=[d2],
            action="create_metric",
        ),
    ]


def _fallback_metric_clarify_options(
    clean_name: str,
    candidate_dims: list[dict[str, Any]],
    has_dim_req: bool,
) -> list[ChatClarificationOption]:
    """Provide rule-based fallback clarification options."""
    concept_opts = _fallback_concept_options(clean_name)
    if concept_opts:
        return concept_opts
    if not has_dim_req:
        return _fallback_logic_only_options(clean_name)
    return _fallback_dimension_options(clean_name, candidate_dims)


def _guidance_clarification_response(clean_name: str) -> dict[str, Any]:
    """Return clarification explaining role boundary when user has no creation/submit rights."""
    msg = (
        f"Hệ thống hiện chưa có chỉ số '{clean_name}'. "
        f"Vai trò hiện tại của bạn không có quyền tạo hoặc gửi đề xuất metric mới. "
        f"Bạn vui lòng liên hệ Data Lead trong workspace để được hỗ trợ."
    )
    interp = SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=msg, options=[]),
        rationale="Người dùng không có quyền tạo hoặc đề xuất metric mới.",
    )
    return {
        "intent": "metric_query",
        "clarification": interp.clarification.model_dump() if interp.clarification else None,
        "interpretation": interp.model_dump(),
        "chat_response": msg,
    }


def _metric_clarification_result(
    clean_name: str, prompt_text: str, options: list[ChatClarificationOption]
) -> dict[str, Any]:
    """Package clarification options into node output format."""
    payload = ChatClarificationPayload(prompt=prompt_text, options=options, target_metric_name=clean_name)
    interp = SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=payload,
        rationale=f"Yêu cầu tạo chỉ số '{clean_name}' cần làm rõ điều kiện tính toán.",
    )
    return {
        "intent": "metric_query",
        "clarification": payload.model_dump(),
        "interpretation": interp.model_dump(),
        "chat_response": prompt_text,
    }


def _concept_clarification_prompt(clean_name: str) -> str:
    """Return transparent intro prompt when concept requires data not fully present."""
    lowered = clean_name.lower()
    if any(k in lowered for k in ["quay lại", "retention", "mua lại", "lặp lại"]):
        return (
            f"Schema hiện tại chưa có dữ liệu lịch sử mua hàng lặp lại để tính chính xác '{clean_name}'. "
            f"Bạn vui lòng chọn một trong các phương án khả thi dưới đây từ dữ liệu hiện có:"
        )
    return f"Để tạo chỉ số '{clean_name}' chuẩn xác, bạn vui lòng chọn phương án tính toán dưới đây:"


def _resolve_clarification_prompt_and_options(
    raw_json: Any,
    default_prompt: str,
    clean_name: str,
    candidate_dims: list[dict[str, Any]],
    has_dim_req: bool,
) -> tuple[str, list[ChatClarificationOption]]:
    """Parse options and enforce transparent prompt for incomplete concepts."""
    prompt_text, options = _parse_metric_clarify_json(raw_json, default_prompt)
    if not options:
        options = _fallback_metric_clarify_options(clean_name, candidate_dims, has_dim_req)
    if any(k in clean_name.lower() for k in ["quay lại", "retention", "mua lại", "lặp lại"]):
        if not any(w in prompt_text.lower() for w in ["chưa có", "lịch sử", "không có", "giới hạn"]):
            prompt_text = default_prompt
    return prompt_text, options


async def _build_metric_creation_clarification(
    state: AgentState, user_message: str, catalog: dict[str, Any]
) -> dict[str, Any]:
    """Prompt LLM or build structured clarification to resolve calculation rules and dimensions."""
    role = (state.get("role", "") or "").lower()
    can_generate = state.get("can_generate_metrics", False)
    clean_name = _clean_metric_name_target(user_message)
    if _missing_metric_action(can_generate, role) == "guidance":
        return _guidance_clarification_response(clean_name)

    has_dim_req = _has_explicit_dimension_intent(user_message)
    candidate_dims = state.get("grounded_candidate_dimensions") or []
    dims_text = _format_candidate_dims_text(candidate_dims)
    schema_text = state.get("semantic_schema_text") or ""
    prompt_llm = _build_metric_clarify_prompt(clean_name, user_message, schema_text, dims_text, has_dim_req)
    default_prompt = _concept_clarification_prompt(clean_name)
    try:
        raw_json = await ainvoke_json(get_llm(), prompt_llm, retries=0)
    except Exception as exc:
        logger.warning("LLM clarification generation failed, using fallback: %s", exc)
        raw_json = None

    prompt_text, options = _resolve_clarification_prompt_and_options(
        raw_json, default_prompt, clean_name, candidate_dims, has_dim_req
    )
    return _metric_clarification_result(clean_name, prompt_text, options)


async def _handle_parse_llm_classification(
    state: AgentState,
    user_message: str,
    catalog: dict[str, Any],
    can_generate: bool,
    role: str,
    grounded_dims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify user query with LLM and dispatch to matching handler."""
    prompt = _build_parse_prompt(state, user_message, catalog, can_generate)
    try:
        raw_json = await ainvoke_json(get_llm(), prompt, retries=1)
        raw_intent = raw_json.get("intent", "semantic_query")
        if raw_intent in {"chitchat", "out_of_scope"}:
            resp = raw_json.get("chat_response") or "Tôi có thể hỗ trợ gì cho bạn về dữ liệu và báo cáo?"
            return {"intent": raw_intent, "chat_response": resp}
        if raw_intent == "metric_query":
            if _is_clarified(state, user_message):
                return {"intent": "metric_query", "chat_response": "Đang đề xuất metric..."}
            return await _build_metric_creation_clarification(state, user_message, catalog)

        interp = _parse_interpretation(raw_json, catalog, can_generate, user_message, role)
        interp = _inject_grounded_options(interp, grounded_dims, catalog, user_message)
        return _build_node_output(interp, intent=raw_intent)
    except Exception as exc:
        logger.warning("Semantic parse node classification failed: %s", exc)
        msg = "Tôi chưa hiểu rõ yêu cầu của bạn do xảy ra lỗi xử lý. Vui lòng thử lại hoặc diễn đạt lại câu hỏi."
        return _build_node_output(_fallback_interpretation(msg))


async def semantic_parse_node(state: AgentState) -> dict[str, Any]:
    """Parse user query: clarify metric creation, guide live queries to explorer, handle chitchat/out_of_scope."""
    catalog = state.get("parser_catalog") or {}
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {"intent": "chitchat", "chat_response": "Bạn chưa nhập câu hỏi. Tôi có thể giúp gì?"}

    pre_intent = state.get("intent")
    if pre_intent in {"chitchat", "out_of_scope"}:
        return {"intent": pre_intent, "chat_response": state.get("chat_response") or "Tôi có thể giúp gì cho bạn?"}

    can_generate = state.get("can_generate_metrics", False)
    if _is_metric_creation_intent(user_message, pre_intent or ""):
        if _is_clarified(state, user_message):
            return {
                "intent": "metric_query",
                "chat_response": "Tôi đang tiến hành tạo Metric Definition theo các tiêu chí đã làm rõ...",
            }
        return await _build_metric_creation_clarification(state, user_message, catalog)

    if not catalog.get("metrics"):
        return _empty_catalog_fallback(can_generate)

    role = state.get("role", "") or ""
    grounded_dims = state.get("grounded_candidate_dimensions") or []
    return await _handle_parse_llm_classification(state, user_message, catalog, can_generate, role, grounded_dims)


def _empty_catalog_fallback(can_generate: bool = False) -> dict[str, Any]:
    """Return polite clarification when no approved metrics exist."""
    msg = "Chưa có Business Metric nào được phê duyệt để truy vấn."
    options = []
    if can_generate:
        msg = f"{msg} Bạn có muốn tạo metric mới từ schema không?"
        options.append(
            ChatClarificationOption(
                id="create_metric",
                label="Tạo metric mới từ schema",
                action="create_metric",
            )
        )
    else:
        msg = f"{msg} Bạn vui lòng duyệt metric trước."
    interp = SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=msg, options=options),
    )
    return {"intent": "semantic_query", "interpretation": interp.model_dump(), "chat_response": msg}


def _build_parse_prompt(
    state: AgentState, user_message: str, catalog: dict[str, Any], can_generate_metrics: bool
) -> str:
    """Format catalog, history, and current Vietnam time into the prompt."""
    now_vn = datetime.now(_VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    history_str = _format_history(state.get("chat_history", []))
    compact_catalog = json.dumps(catalog, ensure_ascii=False, indent=2)

    semantic_schema_text = state.get("semantic_schema_text") or ""
    if not semantic_schema_text:
        candidate_dims = state.get("grounded_candidate_dimensions") or []
        cand_lines = []
        for c in candidate_dims:
            label = c.get("label") or f"{c.get('business_name')} ({c.get('column_name')})"
            samples = c.get("sample_values") or []
            samples_str = f" - Ví dụ: {', '.join(samples)}" if samples else ""
            col_id = c.get("column_id")
            cand_lines.append(f"- Cột '{label}' [column_id={col_id}, hops={c.get('hop_count', 1)}]{samples_str}")
        semantic_schema_text = "\n".join(cand_lines) if cand_lines else "(Không có chiều phân tích mở rộng)"

    if can_generate_metrics:
        role_desc = "Data Lead / Quản trị viên (có quyền tạo và phê duyệt Metric)"
        action_prompt = "đề xuất tạo Business Metric mới"
        action_label = "Tạo Business Metric"
    else:
        role_desc = "Thành viên / Người xem (không có quyền tạo trực tiếp, có quyền gửi yêu cầu đề xuất lên Data Lead)"
        action_prompt = "gửi Data Lead đề xuất Business Metric mới"
        action_label = "Gửi Data Lead đề xuất chỉ số"
    return _PARSE_PROMPT.format(
        current_time=now_vn,
        role_description=role_desc,
        action_prompt=action_prompt,
        action_label=action_label,
        catalog_json=compact_catalog,
        semantic_schema_text=semantic_schema_text,
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


def _is_forced_mismatch(user_message: str, metric_ids: list[int], catalog: dict[str, Any]) -> bool:
    """Detect if distinct concepts (like retention rate) were forcefully mapped to unrelated metrics."""
    lowered = user_message.lower()
    valid_metrics = {m["id"]: m for m in catalog.get("metrics", [])}
    for m_id in metric_ids:
        m = valid_metrics.get(m_id)
        if not m:
            continue
        m_name = (m.get("business_name") or m.get("name") or "").lower()
        if ("giữ chân" in lowered or "retention" in lowered) and (
            "giữ chân" not in m_name and "retention" not in m_name
        ):
            return True
        if ("thuần" in lowered or "net" in lowered) and ("thuần" not in m_name and "net" not in m_name):
            return True
        if ("chuyển đổi" in lowered or "conversion" in lowered) and (
            "chuyển đổi" not in m_name and "conversion" not in m_name
        ):
            return True
        if ("aov" in lowered or "trung bình đơn" in lowered) and (
            "aov" not in m_name and "trung bình" not in m_name and "average" not in m_name
        ):
            return True
    return False


# Generic Vietnamese/English words that carry no distinctive metric meaning.
_CONCEPT_STOPWORDS = frozenset(
    {
        "tỷ",
        "lệ",
        "số",
        "lượng",
        "tổng",
        "theo",
        "của",
        "các",
        "những",
        "và",
        "hoặc",
        "cho",
        "tôi",
        "bạn",
        "xem",
        "báo",
        "cáo",
        "thống",
        "kê",
        "tính",
        "kết",
        "quả",
        "bảng",
        "biểu",
        "năm",
        "tháng",
        "ngày",
        "quý",
        "từng",
        "per",
        "by",
        "rate",
        "ratio",
        "show",
        "view",
        "report",
        "get",
        "give",
    }
)


def _normalize_concept_tokens(text: str) -> set[str]:
    """Extract distinctive lowercase word tokens, dropping generic stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"[^\W\d_]+", text.lower())
    return {t for t in tokens if t not in _CONCEPT_STOPWORDS}


def _requested_concept_matches_catalog(user_message: str, metric_ids: list[int], catalog: dict[str, Any]) -> bool:
    """Return True when the user's requested concept shares a distinctive token with a chosen metric.

    Conservative: if there is no distinctive overlap, the metric was likely force-mapped to an
    unrelated concept, so the caller should treat it as a mismatch. Only applied to Vietnamese
    requests (containing non-ASCII letters) so English-only queries are not wrongly forced to
    clarification when the catalog labels are Vietnamese.
    """
    if not any(ord(ch) > 127 for ch in user_message):
        return True
    requested = _normalize_concept_tokens(user_message)
    if not requested:
        return True
    valid_metrics = {m["id"]: m for m in catalog.get("metrics", [])}
    for m_id in metric_ids:
        m = valid_metrics.get(m_id)
        if not m:
            continue
        label = m.get("business_name") or m.get("name") or ""
        if requested & _normalize_concept_tokens(label):
            return True
    return False


_GROUPING_MARKERS = ("theo ", "by ", "per ", "nhóm theo ", "chia theo ", "phân theo ", "từng ")
_GROUPING_DISCOURSE = frozenset(
    {"như", "tôi", "bạn", "chúng", "ta", "đó", "này", "vậy", "nên", "thì", "đây", "khi", "nếu", "vì"}
)


def _explicitly_requests_grouping(text: str) -> bool:
    """Detect an explicit grouping/dimension request such as 'theo/by/per <dimension>'."""
    if not text:
        return False
    lowered = f" {text.lower()} "
    for marker in _GROUPING_MARKERS:
        idx = lowered.find(marker)
        if idx == -1:
            continue
        rest = lowered[idx + len(marker) :].strip()
        first_word = re.split(r"\s+", rest)[0] if rest else ""
        if first_word and first_word not in _GROUPING_DISCOURSE:
            return True
    return False


def _parse_interpretation(
    raw: dict[str, Any], catalog: dict[str, Any], can_generate_metrics: bool, user_message: str, role: str = ""
) -> SemanticQueryInterpretation:
    """Convert raw LLM dict into validated SemanticQueryInterpretation."""
    status = raw.get("status")
    if status == "resolved":
        spec = _build_spec(raw, catalog)
        if spec is not None:
            if _is_forced_mismatch(user_message, spec.metric_ids, catalog) or not _requested_concept_matches_catalog(
                user_message, spec.metric_ids, catalog
            ):
                raw = {
                    "status": "needs_clarification",
                    "clarification": {
                        "prompt": f"Hệ thống hiện chưa có chỉ số '{user_message.strip()}'.",
                        "options": [],
                    },
                    "rationale": "Chỉ số được hỏi chưa tồn tại chính xác trong danh mục.",
                }
            elif _explicitly_requests_grouping(user_message) and not spec.dimensions:
                raw = {
                    "status": "needs_clarification",
                    "clarification": {
                        "prompt": (
                            "Yêu cầu của bạn cần phân nhóm theo một chiều phân tích. "
                            "Dưới đây là các chiều có sẵn trong dữ liệu, vui lòng chọn một tiêu chí:"
                        ),
                        "options": raw.get("clarification", {}).get("options", []),
                    },
                    "rationale": "Yêu cầu nhóm theo chiều cần làm rõ từ Semantic Layer.",
                }
            else:
                time_ranges = _build_time_ranges(raw.get("time_ranges", []))
                return SemanticQueryInterpretation(
                    status="resolved",
                    spec=spec,
                    time_ranges=time_ranges,
                    rationale=raw.get("rationale"),
                )
    return _build_clarification_interpretation(raw, catalog, can_generate_metrics, user_message, role)


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


def _is_missing_metric_prompt(prompt: str) -> bool:
    """Detect if clarification prompt explains that requested metric is missing."""
    lowered = prompt.lower()
    markers = (
        "chưa có chỉ số",
        "chưa định nghĩa",
        "chưa có metric",
        "không có chỉ số",
        "không có metric",
        "chưa hỗ trợ",
        "chưa có trong",
        "không tồn tại",
    )
    return any(m in lowered for m in markers)


def _extract_metric_name_from_text(text: str) -> str | None:
    """Extract the requested metric name from a clarification prompt or user message.

    Handles quoted names (highest confidence) and common unquoted Vietnamese
    create/request phrases such as "chưa có chỉ số X", "tạo chỉ số X", "đề xuất X".
    """
    if not text:
        return None
    match = re.search(r"['\"`]([^'\"`]{1,120})['\"`]", text)
    if match:
        return match.group(1).strip()
    unquoted = re.search(
        r"(?:chưa có|chưa định nghĩa|không có|không tồn tại)\s+(?:chỉ số|metric|business metric)\s+([^\.!\?]{2,120})"
        r"|(?:tạo|đề xuất|thêm|định nghĩa)\s+(?:chỉ số|metric|business metric)\s+([^\.!\?]{2,120})",
        text,
        flags=re.IGNORECASE,
    )
    if unquoted:
        name = (unquoted.group(1) or unquoted.group(2) or "").strip().strip("'\"`")
        name = re.sub(r"\s+(mới|này|không|được)\s*$", "", name, flags=re.IGNORECASE).strip()
        return name or None
    return None


def _missing_metric_action(can_generate_metrics: bool, role: str) -> str:
    """Resolve the unavailable-metric action for the active role.

    - data_lead -> "create" (save / new Business Metric)
    - member    -> "submit" (propose to Data Lead, stays unverified)
    - admin     -> "guidance" (explain only, no create/submit action)
    When role is unknown, fall back to can_generate_metrics (Data Lead-like vs Member-like).
    """
    role = (role or "").lower()
    if role == "admin":
        return "guidance"
    if role == "data_lead":
        return "create"
    if role == "member":
        return "submit"
    return "create" if can_generate_metrics else "submit"


def _clean_missing_metric_prompt(prompt: str, user_message: str, action: str) -> str:
    """Ensure clarification prompt is clean and concise without listing unrelated metrics."""
    raw_name = _extract_metric_name_from_text(prompt) or _extract_metric_name_from_text(user_message) or user_message
    name = re.sub(
        r"^(xem|cho\s+tôi\s+xem|thống\s+kê|báo\s+cáo|tính)\s+",
        "",
        raw_name.strip(),
        flags=re.IGNORECASE,
    ).strip()
    name = re.sub(r"\s+(tháng\s+này|hôm\s+nay|năm\s+nay|tuần\s+này)$", "", name, flags=re.IGNORECASE).strip()
    if action == "create":
        return f"Hệ thống hiện chưa có chỉ số '{name}'. Bạn có muốn tôi đề xuất tạo Business Metric mới này không?"
    if action == "submit":
        return f"Hệ thống hiện chưa có chỉ số '{name}'. Bạn có muốn gửi Data Lead đề xuất chỉ số này không?"
    return (
        f"Hệ thống hiện chưa có chỉ số '{name}'. "
        f"Chỉ Data Lead mới có quyền tạo hoặc đề xuất chỉ số mới. "
        f"Bạn vui lòng liên hệ Data Lead trong workspace để được hỗ trợ."
    )


def _build_clarification_interpretation(
    raw: dict[str, Any],
    catalog: dict[str, Any],
    can_generate_metrics: bool = False,
    user_message: str = "",
    role: str = "",
) -> SemanticQueryInterpretation:
    """Build a needs_clarification interpretation from clarification payload."""
    clar_data = raw.get("clarification")
    prompt = "Tôi cần thêm thông tin để chạy truy vấn chính xác. Bạn vui lòng chọn một trong các gợi ý dưới đây:"
    options: list[ChatClarificationOption] = []
    if isinstance(clar_data, dict):
        prompt = clar_data.get("prompt") or prompt
        raw_options = clar_data.get("options", [])
        if _is_missing_metric_prompt(prompt):
            action = _missing_metric_action(can_generate_metrics, role)
            prompt = _clean_missing_metric_prompt(prompt, user_message, action)
            if action in ("create", "submit"):
                name = _extract_metric_name_from_text(prompt) or user_message.strip()
                clean_name = re.sub(
                    r"^(xem|cho\s+tôi\s+xem|thống\s+kê|báo\s+cáo|tính)\s+", "", name, flags=re.IGNORECASE
                ).strip()
                label = (
                    f"Tạo Business Metric '{clean_name}'"
                    if action == "create"
                    else f"Gửi Data Lead đề xuất chỉ số '{clean_name}'"
                )
                options.append(
                    ChatClarificationOption(
                        id="create_metric",
                        label=label,
                        description="Yêu cầu AI đề xuất định nghĩa metric này",
                        spec=None,
                        action="create_metric",
                    )
                )
        elif isinstance(raw_options, list):
            valid_ids = {m["id"] for m in catalog.get("metrics", [])}
            for i, opt in enumerate(raw_options):
                if isinstance(opt, dict) and ("label" in opt or "id" in opt):
                    spec_obj = None
                    spec = opt.get("spec")
                    if isinstance(spec, dict) and spec.get("metric_ids"):
                        if set(spec["metric_ids"]).issubset(valid_ids):
                            try:
                                spec_obj = SemanticQuerySpec(**spec)
                            except ValidationError as exc:
                                logger.debug("Skipping invalid option spec: %s", exc)
                                continue
                        else:
                            logger.debug("Skipping option with metric IDs outside approved catalog")
                            continue
                    opt_id = str(
                        opt.get("id")
                        or (
                            f"opt_dim_{spec_obj.dimensions[0].column_id}"
                            if spec_obj and spec_obj.dimensions
                            else f"opt_{i}"
                        )
                    )
                    opt_label = str(opt.get("label") or opt.get("name") or opt_id)
                    try:
                        options.append(
                            ChatClarificationOption(
                                id=opt_id,
                                label=opt_label,
                                description=opt.get("description"),
                                spec=spec_obj,
                                action=opt.get("action"),
                            )
                        )
                    except ValidationError as exc:
                        logger.debug("Skipping invalid option: %s", exc)
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


def _inject_grounded_options(
    interpretation: SemanticQueryInterpretation,
    candidate_dimensions: list[dict[str, Any]],
    catalog: dict[str, Any],
    user_message: str,
) -> SemanticQueryInterpretation:
    """Inject safe multi-hop candidate options with pre-bound query spec."""
    if interpretation.status != "needs_clarification" or not candidate_dimensions:
        return interpretation

    existing_options = interpretation.clarification.options if interpretation.clarification else []
    if any(opt.spec is not None for opt in existing_options):
        return interpretation

    metrics = catalog.get("metrics") or []
    if not metrics:
        return interpretation
    matched_metric = metrics[0]
    u_lower = user_message.lower()
    for m in metrics:
        m_name = (m.get("business_name") or m.get("name") or "").lower()
        if m_name and (m_name in u_lower or u_lower in m_name):
            matched_metric = m
            break
    metric_id = matched_metric["id"]

    user_tokens = [
        w
        for w in re.findall(r"\w+", user_message.lower())
        if len(w) > 1 and w not in {"tính", "xem", "cho", "tôi", "theo", "của", "từng", "báo", "cáo"}
    ]

    def _cand_rank(c: dict[str, Any]) -> int:
        text = f"{c.get('business_name', '')} {c.get('table_business_name', '')} {c.get('column_name', '')}".lower()
        match_count = sum(1 for tok in user_tokens if tok in text)
        return match_count * 10 - c.get("hop_count", 1)

    sorted_cands = sorted(candidate_dimensions, key=_cand_rank, reverse=True)

    new_options: list[ChatClarificationOption] = []
    for cand in sorted_cands[:3]:
        col_id = cand["column_id"]
        label = f"Theo {cand.get('business_name') or cand.get('column_name')}"
        samples = cand.get("sample_values") or []
        desc = f"Ví dụ: {', '.join(samples)}" if samples else f"Bảng {cand.get('table_name')}"
        spec = SemanticQuerySpec(
            metric_ids=[metric_id],
            dimensions=[DimensionSelection(column_id=col_id, time_grain=None)],
            filters=[],
            limit=100,
        )
        new_options.append(
            ChatClarificationOption(
                id=f"opt_dim_{col_id}",
                label=label,
                description=desc,
                spec=spec,
                action=None,
            )
        )

    prompt = (
        interpretation.clarification.prompt
        if interpretation.clarification and "không có trong danh mục" not in interpretation.clarification.prompt
        else "Dữ liệu có thể được phân tích theo các góc nhìn sau. Bạn vui lòng chọn một tiêu chí:"
    )
    return SemanticQueryInterpretation(
        status="needs_clarification",
        clarification=ChatClarificationPayload(prompt=prompt, options=new_options),
        rationale=interpretation.rationale or "Gợi ý các chiều phân tích tiềm năng từ dữ liệu.",
    )


def _build_node_output(
    interpretation: SemanticQueryInterpretation,
    intent: str = "semantic_query",
    chat_response: str | None = None,
) -> dict[str, Any]:
    """Format state update for LangGraph."""
    out: dict[str, Any] = {
        "intent": intent,
    }
    if intent in {"chitchat", "out_of_scope"}:
        out["chat_response"] = chat_response or "Xin chào! Tôi có thể hỗ trợ gì cho bạn?"
        return out

    if intent == "metric_query":
        out["chat_response"] = chat_response or "Tôi sẽ hỗ trợ bạn đề xuất chỉ số này."
        return out

    out["interpretation"] = interpretation.model_dump()
    if interpretation.status == "needs_clarification":
        prompt = interpretation.clarification.prompt if interpretation.clarification else "Vui lòng làm rõ câu hỏi."
        out["chat_response"] = prompt
        out["clarification"] = interpretation.clarification.model_dump() if interpretation.clarification else None
    elif interpretation.status == "resolved":
        out["intent"] = "data_question"
        out["chat_response"] = (
            chat_response
            or "Hệ thống hỗ trợ tra cứu và phân tích số liệu trực tiếp tại tab **Metric Explorer** "
            "với giao diện trực quan và đầy đủ bộ lọc. "
            "Tại đây (AI Studio Chat), tôi hỗ trợ giải thích cấu trúc dữ liệu và tạo/định nghĩa các chỉ số (Business Metric) mới."
        )
    return out
