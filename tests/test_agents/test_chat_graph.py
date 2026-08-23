"""Tests for server-side capability routing in the conversational graph."""

from src.agents.chat_graph import _route_by_intent


def test_metric_query_without_authoring_permission_uses_data_assistant() -> None:
    """Users without metric submission permission must never reach metric generation through chat."""
    state = {"intent": "metric_query", "can_generate_metrics": False}

    assert _route_by_intent(state) == "data_assistant"


def test_metric_query_with_authoring_permission_reaches_metric_generator() -> None:
    """Users with metric submission permission reach the on-demand metric generator."""
    state = {"intent": "metric_query", "can_generate_metrics": True}

    assert _route_by_intent(state) == "metric_query"
