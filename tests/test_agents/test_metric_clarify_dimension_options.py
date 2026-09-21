"""Unit tests verifying optional dimensions and role-based permissions in metric clarify flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.nodes.semantic_parse_node import (
    _has_explicit_dimension_intent,
    semantic_parse_node,
)


def test_has_explicit_dimension_intent():
    """Verify detection of explicit dimension requests in user messages."""
    assert not _has_explicit_dimension_intent("tôi muốn tính tỷ lệ hủy đơn")
    assert not _has_explicit_dimension_intent("tính biên lợi nhuận gộp")
    assert not _has_explicit_dimension_intent("tính aov")
    assert _has_explicit_dimension_intent("tính doanh thu theo vùng")
    assert _has_explicit_dimension_intent("tính tỷ lệ hủy theo kênh bán")
    assert _has_explicit_dimension_intent("xem đơn hàng từng tháng")


@pytest.mark.asyncio
async def test_metric_creation_without_dimensions_no_forced_dimensions_fallback():
    """When user doesn't request dimensions, fallback options must not force '· Gắn chiều' in labels."""
    state = {
        "user_message": "tôi muốn tính tỷ lệ hủy đơn",
        "chat_history": [],
        "grounded_candidate_dimensions": [
            {"column_name": "channel", "business_name": "Kênh bán", "table_name": "orders"},
            {"column_name": "city_name", "business_name": "Khu vực", "table_name": "customers"},
        ],
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", side_effect=RuntimeError("LLM unavailable")):
        result = await semantic_parse_node(state)

    assert result["intent"] == "metric_query"
    assert "clarification" in result
    options = result["clarification"]["options"]
    assert len(options) >= 2
    for opt in options:
        assert "gắn chiều" not in opt["label"].lower()
        assert opt["dimensions"] == []


@pytest.mark.asyncio
async def test_metric_creation_with_explicit_dimensions_fallback():
    """When user explicitly requests dimensions, fallback options suggest corresponding dimensions."""
    state = {
        "user_message": "tôi muốn tính doanh thu theo vùng",
        "chat_history": [],
        "grounded_candidate_dimensions": [
            {"column_name": "region_name", "business_name": "Khu vực", "table_name": "customers"},
            {"column_name": "channel", "business_name": "Kênh bán", "table_name": "orders"},
        ],
        "can_generate_metrics": True,
        "role": "data_lead",
    }

    with patch("src.agents.nodes.semantic_parse_node.ainvoke_json", side_effect=RuntimeError("LLM unavailable")):
        result = await semantic_parse_node(state)

    assert result["intent"] == "metric_query"
    assert "clarification" in result
    options = result["clarification"]["options"]
    assert len(options) >= 2
    assert any("Khu vực" in opt["label"] or "Theo" in opt["label"] for opt in options)
    assert any(len(opt["dimensions"]) > 0 for opt in options)


@pytest.mark.asyncio
async def test_metric_creation_admin_role_guidance_no_create_options():
    """Admin role without metric creation permission receives guidance and no creation options."""
    state = {
        "user_message": "tôi muốn tính tỷ lệ hủy đơn",
        "chat_history": [],
        "can_generate_metrics": False,
        "role": "admin",
    }

    result = await semantic_parse_node(state)

    assert result["intent"] == "metric_query"
    assert "không có quyền tạo hoặc gửi đề xuất" in result["chat_response"]
    assert result["clarification"]["options"] == []
