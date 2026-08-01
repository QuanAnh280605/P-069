"""Save Node — Flow 1 Step 5 (after HITL approval).

Lưu toàn bộ Semantic Layer (enriched_schema + approved metrics) vào
Metadata Store (PostgreSQL) vào các bảng:
  - semantic_tables
  - semantic_columns
  - semantic_metrics
"""
from __future__ import annotations

from src.agents.state import AgentState


async def save_node(state: AgentState) -> dict:
    """Persist approved Semantic Layer to Metadata Store.

    Input state fields: db_id, enriched_schema, suggested_metrics, hitl_approved
    Output state fields: semantic_layer_id | error
    """
    if not state.get("hitl_approved"):
        return {"error": "save_node: HITL not approved, cannot save"}

    # TODO: Implement steps:
    # 1. Open SQLAlchemy session to Metadata Store (not Target DB)
    # 2. Upsert semantic_tables records from enriched_schema
    # 3. Upsert semantic_columns records from enriched_schema
    # 4. Insert approved metrics into semantic_metrics
    # 5. Commit and return semantic_layer_id
    return {
        "semantic_layer_id": -1,
        "error": "save_node: not yet implemented",
    }
