"""Conversational orchestrator graph — routes chitchat vs metric generation."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.nodes.chitchat_node import chitchat_node
from src.agents.nodes.data_assistant_node import data_assistant_node
from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.agents.nodes.orchestrator_node import orchestrator_node
from src.agents.state import AgentState


def _route_by_intent(state: AgentState) -> str:
    """Route to the permitted assistant capability for the classified intent."""
    intent = state.get("intent", "chitchat")
    # If orchestrator already wrote a chat_response (e.g. empty message fallback)
    # skip downstream nodes and go straight to END
    if state.get("chat_response"):
        return "chitchat_done"
    if intent == "metric_query" and not state.get("can_generate_metrics", False):
        return "data_assistant"
    return intent


def build_chat_graph() -> StateGraph:
    """Build multi-agent conversational orchestrator graph.

    Flow:
        orchestrator → chitchat       (for general / greeting questions)
        orchestrator → data_assistant (for read-only data questions)
        orchestrator → metric_suggest (for authorized metric authoring)
    """
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
            "data_assistant": "data_assistant",
            "chitchat_done": END,
            "metric_query": "metric_suggest",
        },
    )
    graph.add_edge("chitchat", END)
    graph.add_edge("metric_suggest", END)

    return graph.compile()


chat_agent = build_chat_graph()
