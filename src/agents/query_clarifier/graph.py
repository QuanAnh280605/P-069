"""LangGraph graph construction for the Guided Wizard Query Clarifier Agent."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.query_clarifier.nodes.resolve_node import resolve_node
from src.agents.query_clarifier.nodes.wizard_init_node import wizard_init_node
from src.agents.query_clarifier.nodes.wizard_step_node import wizard_step_node
from src.agents.query_clarifier.state import QueryClarifierState


def route_after_step(state: QueryClarifierState) -> str:
    """Route to resolve if step is completed, step2 for dimensions, or END on error."""
    if state.get("error_message"):
        return END
    step = state.get("current_step", 1)
    if step == 2:
        return "resolve"
    return END


def build_clarifier_graph() -> StateGraph:
    """Construct the Guided Wizard StateGraph pipeline."""
    graph = StateGraph(QueryClarifierState)

    graph.add_node("wizard_init", wizard_init_node)
    graph.add_node("wizard_step", wizard_step_node)
    graph.add_node("resolve", resolve_node)

    graph.set_entry_point("wizard_init")
    graph.add_edge("wizard_init", END)
    graph.add_edge("wizard_step", "resolve")
    graph.add_edge("resolve", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


clarifier_agent = build_clarifier_graph()
