---
title: "State Management"
description: "Định nghĩa State schema cho LangGraph Flow 1 pipeline"
weight: 1
---

## State Schema — P-069

State là "bộ nhớ" của agent, truyền giữa các nodes trong Flow 1 pipeline:

```python
from typing import Any, TypedDict

class AgentState(TypedDict, total=False):
    # Input
    db_id: int                    # ID của semantic_databases record
    conn_url_enc: str             # Connection URL đã Fernet encrypt

    # Flow 1 — Introspect Node output
    raw_schema: dict[str, Any]    # Schema kỹ thuật thô từ Inspector

    # Flow 1 — Enrich Node output
    enriched_schema: dict[str, Any]  # Schema + business_name + description

    # Flow 1 — MetricSuggest Node output
    suggested_metrics: list[dict[str, Any]]  # Business Metrics do LLM đề xuất

    # Flow 1 — HITL Interrupt
    hitl_approved: bool           # True nếu BA/DA đã duyệt

    # Flow 1 — Save Node output
    semantic_layer_id: int        # ID của Semantic Layer đã lưu

    # Shared — error handling
    error: str                    # Thông báo lỗi nếu có
```

## Nguyên tắc thiết kế State

### 1. Dùng TypedDict

```python
# ✅ TỐT — TypedDict cho state
class AgentState(TypedDict, total=False):
    db_id: int
    raw_schema: dict[str, Any]

# ❌ TỆ — Không dùng Pydantic cho LangGraph state
class AgentState(BaseModel):
    db_id: int  # LangGraph expects TypedDict
```

### 2. total=False cho optional fields

```python
class AgentState(TypedDict, total=False):
    db_id: int                # Input (luôn có)
    raw_schema: dict          # Optional — chỉ có sau introspect
    error: str                # Optional — chỉ có khi lỗi
```

### 3. Chỉ thêm fields thực sự cần

- Mỗi field = data được truyền giữa nodes
- Không dùng state như "trash can" chứa mọi thing
- Fields theo thứ tự: db_id → raw_schema → enriched_schema → suggested_metrics → hitl_approved → semantic_layer_id

### 4. State update pattern

```python
# Mỗi node chỉ return fields nó thay đổi
async def enrich_node(state: AgentState) -> dict:
    raw_schema = state.get("raw_schema", {})
    enriched = await llm_enrich(raw_schema)
    return {"enriched_schema": enriched}  # Chỉ update "enriched_schema"
```
