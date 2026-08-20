"""Tests for direct conversational graph routing."""

from src.agents.chat_graph import _route_by_intent


def test_metric_query_reaches_metric_generator_for_member() -> None:
    """Metric requests never fall through to data guidance."""
    assert _route_by_intent({"intent": "metric_query", "can_generate_metrics": False}) == "metric_query"


def test_metric_query_reaches_metric_generator_for_data_lead() -> None:
    """Data Leads use the same metric-generation route."""
    assert _route_by_intent({"intent": "metric_query", "can_generate_metrics": True}) == "metric_query"


def test_data_question_reaches_data_assistant() -> None:
    """Schema questions remain on the data-assistant route."""
    assert _route_by_intent({"intent": "data_question"}) == "data_question"
