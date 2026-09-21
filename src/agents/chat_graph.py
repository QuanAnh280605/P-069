"""Conversational orchestrator graph for data guidance and metric proposals."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.nodes.chitchat_node import chitchat_node
from src.agents.nodes.data_assistant_node import data_assistant_node
from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.agents.nodes.orchestrator_node import orchestrator_node
from src.agents.nodes.semantic_parse_node import semantic_parse_node
from src.agents.state import AgentState


def _route_by_intent(state: AgentState) -> str:
    """Route the server-classified intent without a metric-decision gate."""
    if state.get("chat_response"):
        return "chitchat_done"
    intent = state.get("intent", "chitchat")
    if intent == "out_of_scope":
        return "chitchat_done"
    if intent in {"semantic_query", "metric_query"}:
        return "semantic_parse"
    return intent


def _route_after_parse(state: AgentState) -> str:
    """Route from semantic_parse to metric_suggest only if a genuine unclarified metric proposal is needed."""
    if state.get("intent") == "metric_query" and not state.get("clarification"):
        return "metric_suggest"
    return "done"


def build_chat_graph() -> StateGraph:
    """Build the direct chitchat, data-assistant, metric-proposal, and semantic-query flows."""
    graph = StateGraph(AgentState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("chitchat", chitchat_node)
    graph.add_node("data_assistant", data_assistant_node)
    graph.add_node("metric_suggest", on_demand_metric_suggest_node)
    graph.add_node("semantic_parse", semantic_parse_node)
    graph.set_entry_point("orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _route_by_intent,
        {
            "chitchat": "chitchat",
            "data_question": "data_assistant",
            "semantic_parse": "semantic_parse",
            "out_of_scope": END,
            "chitchat_done": END,
        },
    )
    graph.add_edge("chitchat", END)
    graph.add_edge("data_assistant", END)
    graph.add_edge("metric_suggest", END)
    graph.add_conditional_edges(
        "semantic_parse",
        _route_after_parse,
        {
            "metric_suggest": "metric_suggest",
            "done": END,
        },
    )
    return graph.compile()


chat_agent = build_chat_graph()
