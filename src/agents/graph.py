from langgraph.graph import END, StateGraph

from src.agents.nodes.enrich_node import enrich_node
from src.agents.nodes.introspect_node import introspect_node
from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node
from src.agents.nodes.save_node import save_node
from src.agents.state import AgentState


def route_after_introspect(state: AgentState) -> str:
    """Route to enrich if introspect succeeded, else terminate with error."""
    if state.get("error"):
        return END
    return "enrich"


def route_after_save(state: AgentState) -> str:
    """Route after save: saved → END, rejected → re-enrich."""
    if state.get("semantic_layer_id"):
        return END
    return "enrich"


def build_graph() -> StateGraph:
    """Build Flow 1 LangGraph pipeline.

    Pipeline: introspect → enrich → metric_suggest (on-demand/optional) → save (interrupt_before)
    When the graph reaches the save node it pauses so external code can set
    ``hitl_approved`` on the state and resume (approve) or leave it False
    (reject → loop back to enrich).
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("introspect", introspect_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("metric_suggest", on_demand_metric_suggest_node)  # On-demand AI metric suggestion
    graph.add_node("save", save_node)

    # Edges
    graph.set_entry_point("introspect")
    graph.add_conditional_edges("introspect", route_after_introspect)
    graph.add_edge("enrich", "metric_suggest")
    graph.add_edge("metric_suggest", "save")
    graph.add_conditional_edges("save", route_after_save)

    return graph.compile(interrupt_before=["save"])


agent = build_graph()
