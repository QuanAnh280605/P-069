"""Conversational orchestrator graph for data guidance and metric proposals."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.nodes.chitchat_node import chitchat_node
from src.agents.nodes.data_assistant_node import data_assistant_node
from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.agents.nodes.orchestrator_node import orchestrator_node
from src.agents.state import AgentState


def _route_by_intent(state: AgentState) -> str:
    """Route the server-classified intent without a metric-decision gate."""
    if state.get("chat_response"):
        return "chitchat_done"
    return state.get("intent", "chitchat")


def build_chat_graph() -> StateGraph:
    """Build the direct chitchat, data-assistant, and metric-proposal flows."""
    graph = StateGraph(AgentState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("chitchat", chitchat_node)
    graph.add_node("data_assistant", data_assistant_node)
    graph.add_node("metric_suggest", on_demand_metric_suggest_node)
    graph.set_entry_point("orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        _route_by_intent,
        {
            "chitchat": "chitchat",
            "data_question": "data_assistant",
            "metric_query": "metric_suggest",
            "chitchat_done": END,
        },
    )
    graph.add_edge("chitchat", END)
    graph.add_edge("data_assistant", END)
    graph.add_edge("metric_suggest", END)
    return graph.compile()


chat_agent = build_chat_graph()
