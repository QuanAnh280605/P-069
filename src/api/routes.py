from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.models.db import UserModel
from src.models.schema_metadata import DiagnosticCode, SchemaDialect
from src.models.schemas import (
    ApproveRequest,
    ApproveResponse,
    GenerateRequest,
    GenerateResponse,
    ImportedSchemaCreateRequest,
    ImportedSchemaResponse,
    ImportedSchemaSummaryResponse,
    LiveDbConnectRequest,
    LiveDbResponse,
    LiveDbSummaryResponse,
    MetricCreate,
    MetricResponse,
    MetricUpdate,
    SemanticColumnUpdate,
    SemanticTableUpdate,
    SqlDumpPreviewResponse,
)
from src.services.database import get_db_session
from src.services.export_service import build_semantic_layer_dict, serialize_to_json, serialize_to_yaml
from src.services.imported_schema_service import (
    create_imported_schema,
    delete_imported_schema,
    get_imported_schema,
    list_imported_schemas,
)
from src.services.live_db_service import (
    create_live_target_db,
    delete_live_target_db,
    get_live_target_db,
    list_live_target_dbs,
)
from src.services.schema_ingestion import parse_sql_dump_preview
from src.services.sql_dump_parser_models import SqlDumpParseError
from src.services.sql_dump_scanner_models import SqlDumpScanError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/semantic/import/preview", response_model=SqlDumpPreviewResponse)
async def import_sql_dump_preview(
    request: Request,
    filename: str = Header(..., alias="X-Filename"),
    dialect: SchemaDialect | None = Header(default=None, alias="X-SQL-Dialect"),
) -> SqlDumpPreviewResponse:
    """Parse an SQL dump body into technical schema metadata."""
    _validate_preview_content_type(request)
    try:
        return await parse_sql_dump_preview(request.stream(), filename, dialect)
    except (SqlDumpScanError, SqlDumpParseError) as error:
        _raise_preview_parse_error(error)


def _validate_preview_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"application/sql", "text/plain"}:
        raise HTTPException(status_code=415, detail="SQL dump content type is required")


def _raise_preview_parse_error(error: SqlDumpScanError | SqlDumpParseError) -> NoReturn:
    diagnostic = error.diagnostic
    raise HTTPException(
        status_code=_preview_error_status(diagnostic.code),
        detail=diagnostic.model_dump(mode="json"),
    ) from error


def _preview_error_status(code: DiagnosticCode) -> int:
    if code in {DiagnosticCode.FILE_TOO_LARGE, DiagnosticCode.STATEMENT_TOO_LARGE}:
        return 413
    if code in {DiagnosticCode.EMPTY_FILE, DiagnosticCode.INVALID_EXTENSION, DiagnosticCode.INVALID_ENCODING}:
        return 400
    return 422


@router.post("/semantic/import/saved", response_model=ImportedSchemaResponse, status_code=201)
async def save_imported_schema(
    body: ImportedSchemaCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ImportedSchemaResponse:
    """Persist parsed schema metadata under a user-provided display name."""
    return await create_imported_schema(db, current_user.id, body.display_name, body.raw_schema)


@router.get("/semantic/import/saved", response_model=list[ImportedSchemaSummaryResponse])
async def get_saved_imported_schemas(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ImportedSchemaSummaryResponse]:
    """List imported schemas owned by the authenticated user."""
    return await list_imported_schemas(db, current_user.id)


@router.get("/semantic/import/saved/{schema_id}", response_model=ImportedSchemaResponse)
async def get_saved_imported_schema(
    schema_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ImportedSchemaResponse:
    """Load one user-owned imported schema for preview."""
    record = await get_imported_schema(db, current_user.id, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved schema not found")
    return record


@router.delete("/semantic/import/saved/{schema_id}", status_code=204)
async def remove_saved_imported_schema(
    schema_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete one user-owned imported schema."""
    if not await delete_imported_schema(db, current_user.id, schema_id):
        raise HTTPException(status_code=404, detail="Saved schema not found")


# ---------------------------------------------------------------------------
# Live Target Database Management (Zero-Data Introspection)
# ---------------------------------------------------------------------------


@router.post("/semantic/db/connect", response_model=LiveDbResponse, status_code=201)
async def connect_live_target_db(
    body: LiveDbConnectRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LiveDbResponse:
    """Connect to a live target database, encrypt URL, introspect schema without SELECT data, and persist."""
    try:
        return await create_live_target_db(
            db,
            current_user.id,
            body.display_name,
            body.dialect,
            body.conn_url,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to connect and introspect target database: {exc}") from exc


@router.get("/semantic/db/saved", response_model=list[LiveDbSummaryResponse])
async def get_saved_live_target_dbs(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[LiveDbSummaryResponse]:
    """List live target databases connected and saved by the user."""
    return await list_live_target_dbs(db, current_user.id)


@router.get("/semantic/db/saved/{db_id}", response_model=LiveDbResponse)
async def get_saved_live_target_db(
    db_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LiveDbResponse:
    """Get details and raw schema metadata of a saved live target database."""
    record = await get_live_target_db(db, current_user.id, db_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved live database not found")
    return record


@router.delete("/semantic/db/saved/{db_id}", status_code=204)
async def remove_saved_live_target_db(
    db_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a saved live target database connection."""
    if not await delete_live_target_db(db, current_user.id, db_id):
        raise HTTPException(status_code=404, detail="Saved live database not found")


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
