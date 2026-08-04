---
title: "Nodes & Edges"
description: "Định nghĩa nodes và edges trong LangGraph Flow 1 pipeline"
weight: 2
---

## Nodes — P-069 Flow 1

Mỗi node là một hàm async nhận state, trả về dict:

```python
async def enrich_node(state: AgentState) -> dict:
    """Enrich schema with business_name + description via LLM."""
    raw_schema = state.get("raw_schema", {})
    if not raw_schema:
        return {"error": "raw_schema is empty"}
    enriched = await llm_enrich_batch(raw_schema)
    return {"enriched_schema": enriched}
```

### Flow 1 Pipeline Nodes

| Node | File | Responsibility |
|------|------|---------------|
| `introspect_node` | `src/agents/nodes/introspect_node.py` | SQLAlchemy Inspector → raw_schema |
| `enrich_node` | `src/agents/nodes/enrich_node.py` | LLM → business_name + description |
| `metric_suggest_node` | `src/agents/nodes/metric_suggest_node.py` | LLM → Business Metrics |
| `save_node` | `src/agents/nodes/save_node.py` | Persist to Metadata Store |

### Node Best Practices

1. **Một node một trách nhiệm** — Không làm 2 việc trong 1 node
2. **Return chỉ fields cần update** — Không return toàn bộ state
3. **Error handling** — Luôn có try/except và set error field
4. **Docstring** — Mô tả node làm gì
5. **Dùng `get_llm()`** từ `src/services/llm.py` — không tạo ChatOpenAI trực tiếp

```python
async def safe_enrich_node(state: AgentState) -> dict:
    """Enrich schema, handle errors gracefully."""
    try:
        raw_schema = state.get("raw_schema", {})
        result = await llm_enrich(raw_schema)
        return {"enriched_schema": result}
    except Exception as e:
        return {"error": f"Enrich failed: {e}"}
```

## Edges

### Linear Edges

```python
graph.add_edge("enrich", "metric_suggest")
```

### Conditional Edges (Routing)

```python
def route_after_hitl(state: AgentState) -> str:
    """Route based on HITL decision."""
    if state.get("hitl_approved"):
        return "save"
    return "enrich"  # Re-enrich if rejected

graph.add_conditional_edges("metric_suggest", route_after_hitl)
```

## Graph Construction

```python
from langgraph.graph import END, StateGraph

def build_graph() -> StateGraph:
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
```

## Pipeline Flow

```
DB Connection URL
    → Introspect Node (SQLAlchemy Inspector)
    → Enrich Node (LLM batch)
    → Metric Suggest Node (LLM)
    → HITL Interrupt (BA/DA review)
    → Save Node (persist to Metadata Store)
    → Semantic Layer (JSON/YAML)
```
