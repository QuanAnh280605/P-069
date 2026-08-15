"""Node for initializing Step 1 of the Guided Wizard (Metric Selection)."""

from __future__ import annotations

from typing import Any

from src.agents.query_clarifier.state import QueryClarifierState, QueryClarifyOption, WizardStepOutput


async def wizard_init_node(state: QueryClarifierState) -> dict[str, Any]:
    """Build initial wizard step presenting approved metrics as solid radio buttons."""
    metrics = state.get("approved_metrics", [])
    if not metrics:
        return {
            "current_step": 1,
            "error_message": "Không tìm thấy chỉ số (metric) nào đã được phê duyệt trong database này.",
            "wizard_step": WizardStepOutput(
                step=1,
                title="Chọn Chỉ Số Nghiệp Vụ",
                question="Hiện tại chưa có chỉ số nghiệp vụ nào được phê duyệt.",
                options=[],
                is_completed=False,
            ),
        }

    options: list[QueryClarifyOption] = []
    for m in metrics:
        m_id = m.get("metric_id") or m.get("id")
        name = m.get("name") or f"Metric #{m_id}"
        desc = m.get("description") or ""
        options.append(
            QueryClarifyOption(
                id=f"metric:{m_id}",
                label=name,
                description=desc,
            )
        )

    wizard_step = WizardStepOutput(
        step=1,
        title="Bước 1: Chọn Chỉ Số Nghiệp Vụ",
        question="Bạn muốn theo dõi và phân tích chỉ số nghiệp vụ nào dưới đây?",
        options=options,
        is_completed=False,
    )

    return {
        "current_step": 1,
        "wizard_step": wizard_step,
        "error_message": None,
    }
