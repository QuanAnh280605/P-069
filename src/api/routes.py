from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.config import get_settings
from src.models.db import UserModel
from src.models.schema_metadata import DiagnosticCode, SchemaDialect
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
    SqlDumpPreviewApprovalResponse,
    SqlDumpPreviewResponse,
)
from src.services.database import get_db_session
from src.services.export_service import build_semantic_layer_dict, serialize_to_json, serialize_to_yaml
from src.services.preview_draft_store import (
    InMemoryPreviewDraftStore,
    PreviewDraftCapacityError,
    PreviewDraftNotFoundError,
    get_preview_draft_store,
)
from src.services.schema_ingestion import create_sql_dump_preview
from src.services.sql_dump_parser import SqlDumpParseError
from src.services.sql_dump_scanner import SqlDumpScanError

router = APIRouter(dependencies=[Depends(get_current_user)])

PreviewStore = Annotated[InMemoryPreviewDraftStore, Depends(get_preview_draft_store)]
CurrentUser = Annotated[UserModel, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Flow 1 — Generate & HITL
# ---------------------------------------------------------------------------


@router.post("/semantic/import/preview", response_model=SqlDumpPreviewResponse, status_code=202)
async def import_sql_dump_preview(
    request: Request,
    current_user: CurrentUser,
    draft_store: PreviewStore,
    filename: str = Header(..., alias="X-Filename", min_length=1, max_length=255),
    dialect: SchemaDialect | None = Header(default=None, alias="X-SQL-Dialect"),
) -> SqlDumpPreviewResponse:
    """Parse a raw SQL file body into an owner-bound non-persistent preview."""
    _require_preview_enabled()
    _validate_preview_content_type(request)
    try:
        return await create_sql_dump_preview(request.stream(), filename, current_user.id, draft_store, dialect)
    except (SqlDumpScanError, SqlDumpParseError) as error:
        _raise_preview_parse_error(error)
    except PreviewDraftCapacityError as error:
        raise HTTPException(status_code=503, detail="Preview draft capacity reached") from error


@router.get("/semantic/import/drafts/{draft_id}", response_model=SqlDumpPreviewResponse)
async def get_sql_dump_preview(
    draft_id: str,
    current_user: CurrentUser,
    draft_store: PreviewStore,
) -> SqlDumpPreviewResponse:
    """Return a live preview only to its authenticated owner."""
    _require_preview_enabled()
    try:
        return await draft_store.get(current_user.id, draft_id)
    except PreviewDraftNotFoundError as error:
        raise HTTPException(status_code=404, detail="Preview draft not found or expired") from error


@router.post(
    "/semantic/import/drafts/{draft_id}/approve",
    response_model=SqlDumpPreviewApprovalResponse,
)
async def approve_sql_dump_preview(
    draft_id: str,
    current_user: CurrentUser,
    draft_store: PreviewStore,
) -> SqlDumpPreviewApprovalResponse:
    """Approve a preview in memory without invoking Save Node or persistence."""
    _require_preview_enabled()
    try:
        draft = await draft_store.approve(current_user.id, draft_id)
    except PreviewDraftNotFoundError as error:
        raise HTTPException(status_code=404, detail="Preview draft not found or expired") from error
    return SqlDumpPreviewApprovalResponse(draft=draft)


def _require_preview_enabled() -> None:
    settings = get_settings()
    if not settings.sql_dump_preview_enabled or settings.app_env == "production":
        raise HTTPException(status_code=404, detail="SQL dump preview is disabled")


def _validate_preview_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    allowed = {"application/sql", "text/plain", "application/octet-stream"}
    if content_type not in allowed:
        raise HTTPException(status_code=415, detail="Preview expects a raw SQL file body")


def _raise_preview_parse_error(error: SqlDumpScanError | SqlDumpParseError) -> NoReturn:
    diagnostic = error.diagnostic
    status_code = 413 if diagnostic.code == DiagnosticCode.FILE_TOO_LARGE else 422
    validation_codes = {
        DiagnosticCode.EMPTY_FILE,
        DiagnosticCode.INVALID_EXTENSION,
        DiagnosticCode.INVALID_ENCODING,
    }
    if diagnostic.code in validation_codes:
        status_code = 400
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": diagnostic.code.value,
            "message": diagnostic.message,
            "statement_index": diagnostic.statement_index,
            "line": diagnostic.line,
            "column": diagnostic.column,
        },
    ) from error


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
