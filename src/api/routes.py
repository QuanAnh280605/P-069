from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.schemas import (
    ApproveRequest,
    ApproveResponse,
    GenerateRequest,
    GenerateResponse,
    MetricCreate,
    MetricResponse,
    MetricUpdate,
    SemanticColumnUpdate,
    SemanticTableUpdate,
)
from src.services.database import get_db_session
from src.services.export_service import build_semantic_layer_dict, serialize_to_json, serialize_to_yaml

router = APIRouter(dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Flow 1 — Generate & HITL
# ---------------------------------------------------------------------------


@router.post("/semantic/generate", response_model=GenerateResponse, status_code=202)
async def generate_semantic_layer(request: GenerateRequest) -> GenerateResponse:
    """Kick-off Flow 1: Introspect → Enrich → MetricSuggest → HITL interrupt.

    Returns draft semantic layer (status=pending_review). BA/DA review inline
    then call POST /semantic/approve to persist.
    """
    # TODO: invoke LangGraph Flow 1 graph with db_id
    raise HTTPException(status_code=501, detail="Flow 1 pipeline not yet implemented")


@router.post("/semantic/approve", response_model=ApproveResponse)
async def approve_semantic_layer(request: ApproveRequest) -> ApproveResponse:
    """HITL approval — Save Node: persist reviewed semantic layer to Metadata Store."""
    # TODO: resume LangGraph graph from HITL interrupt checkpoint
    raise HTTPException(status_code=501, detail="HITL approval not yet implemented")


# ---------------------------------------------------------------------------
# HITL Inline Edit — Tables & Columns
# ---------------------------------------------------------------------------


@router.put("/semantic/{db_id}/table/{table_name}", status_code=200)
async def update_table(
    db_id: int,
    table_name: str,
    body: SemanticTableUpdate,
) -> dict:
    """Update business_name & description for a table (HITL inline edit)."""
    # TODO: update semantic_tables record in Metadata Store
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.put("/semantic/{db_id}/column/{table_name}/{column_name}", status_code=200)
async def update_column(
    db_id: int,
    table_name: str,
    column_name: str,
    body: SemanticColumnUpdate,
) -> dict:
    """Update business_name & description for a column (HITL inline edit)."""
    # TODO: update semantic_columns record in Metadata Store
    raise HTTPException(status_code=501, detail="Not yet implemented")


# ---------------------------------------------------------------------------
# Business Metrics CRUD
# ---------------------------------------------------------------------------


@router.post("/semantic/{db_id}/metric", response_model=MetricResponse, status_code=201)
async def create_metric(db_id: int, body: MetricCreate) -> MetricResponse:
    """Create a new Business Metric (manual or AI-suggested)."""
    # TODO: insert into semantic_metrics
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.put("/semantic/{db_id}/metric/{metric_id}", response_model=MetricResponse)
async def update_metric(db_id: int, metric_id: int, body: MetricUpdate) -> MetricResponse:
    """Update an existing Business Metric."""
    # TODO: update semantic_metrics record
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.delete("/semantic/{db_id}/metric/{metric_id}", status_code=204)
async def delete_metric(db_id: int, metric_id: int) -> None:
    """Delete a Business Metric."""
    # TODO: delete from semantic_metrics
    raise HTTPException(status_code=501, detail="Not yet implemented")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.get("/semantic/{db_id}/export")
async def export_semantic_layer(
    db_id: int,
    format: str = "json",
    db: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """Export approved Semantic Layer as JSON or YAML file download.

    Query param: format=json|yaml
    """
    if format not in ("json", "yaml"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'yaml'")

    try:
        layer = await build_semantic_layer_dict(db, db_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if format == "yaml":
        content = serialize_to_yaml(layer)
        media_type = "text/yaml"
    else:
        content = serialize_to_json(layer)
        media_type = "application/json"

    return PlainTextResponse(content=content, media_type=media_type)


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def agent_status() -> dict:
    """Check agent readiness."""
    return {"status": "ready", "pipeline": "Flow 1 — Generate & Manage Semantic Layer"}
