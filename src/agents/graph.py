from langgraph.graph import END, StateGraph

from src.agents.nodes.enrich_node import enrich_node
from src.agents.nodes.introspect_node import introspect_node
from src.agents.nodes.metric_suggest_node import metric_suggest_node
from src.agents.nodes.save_node import save_node
from src.agents.state import AgentState


def route_after_introspect(state: AgentState) -> str:
    """Route to enrich if introspect succeeded, else terminate with error."""
    if state.get("error"):
        return END
    return "enrich"


def route_after_hitl(state: AgentState) -> str:
    """Route based on HITL decision: approved → save, else → re-enrich."""
    if state.get("hitl_approved"):
        return "save"
    return "enrich"


def build_graph() -> StateGraph:
    """Build Flow 1 LangGraph pipeline.

    Pipeline: introspect → enrich → metric_suggest → HITL interrupt → save
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("introspect", introspect_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("metric_suggest", metric_suggest_node)
    graph.add_node("save", save_node)

    # Edges
    graph.set_entry_point("introspect")
    graph.add_conditional_edges("introspect", route_after_introspect)
    graph.add_edge("enrich", "metric_suggest")
    graph.add_conditional_edges("metric_suggest", route_after_hitl)
    graph.add_edge("save", END)

    return graph.compile()


agent = build_graph()
