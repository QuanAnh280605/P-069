"""API Routes for Semantic Layer Flow 1, Business Metrics, Live DB, and HITL inline edits."""

import asyncio
import logging
import re
import uuid
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_current_user
from src.config import get_settings
from src.models.db import (
    CanonicalRelationshipModel,
    ChatMessageModel,
    ChatSessionModel,
    ImportedSchemaModel,
    LiveTargetDbModel,
    MetricRequestModel,
    MetricVersionModel,
    OrganizationMemberModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.metric_definition import MetricDefinition
from src.models.review_mixin import REVIEW_STATUS_APPROVED
from src.models.schema_metadata import DiagnosticCode, RawSchemaMetadata, SchemaDialect
from src.models.schemas import (
    ApproveRequest,
    CanonicalRelationshipResponse,
    ChatClarificationPayload,
    ChatClarificationSelection,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSemanticQueryResult,
    ChatSessionDetailResponse,
    ChatSessionSummaryResponse,
    ChatSessionUpdateRequest,
    ClarificationResolution,
    CustomMetricGenerateRequest,
    CustomMetricGenerateResponse,
    GenerateRequest,
    ImportedSchemaCreateRequest,
    ImportedSchemaResponse,
    ImportedSchemaSummaryResponse,
    JoinPathOption,
    LiveDbConnectRequest,
    LiveDbResponse,
    LiveDbSummaryResponse,
    MetricCreate,
    MetricDimensionsResponse,
    MetricFilterColumnsResponse,
    MetricHistoryResponse,
    MetricListItem,
    MetricRequestCreate,
    MetricRequestResponse,
    MetricRequestReview,
    MetricResponse,
    MetricUpdate,
    MetricUpdateResponse,
    MetricVersionItem,
    MetricVersionResponse,
    NotificationListResponse,
    NotificationResponse,
    SemanticApproveV2Response,
    SemanticCatalogColumn,
    SemanticCatalogResponse,
    SemanticCatalogTable,
    SemanticColumnUpdate,
    SemanticGenerateV2Response,
    SemanticQueryCompileResponse,
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticQuerySpec,
    SemanticTableUpdate,
    SqlDumpPreviewResponse,
)
from src.services.chat_service import (
    ChatAuthorizationError,
    ClarificationAlreadyResolvedError,
    auto_generate_session_title,
    create_chat_session,
    delete_chat_session,
    get_chat_database,
    get_chat_message,
    get_chat_message_by_client_id,
    get_chat_messages_page,
    get_chat_session,
    get_chat_session_with_messages,
    get_recent_chat_history,
    list_chat_sessions,
    resolve_clarification_message,
    save_chat_message,
    update_chat_session_title,
)
from src.services.database import decrypt_conn_url, get_db_session, get_session_factory
from src.services.dimension_recommender import get_dimensions_for_metric, get_filter_columns_for_metric
from src.services.export_service import build_semantic_layer_dict, serialize_to_json, serialize_to_yaml
from src.services.imported_schema_service import (
    create_imported_schema,
    delete_imported_schema,
    get_imported_schema,
    list_imported_schemas,
)
from src.services.join_path_service import join_path_options
from src.services.live_db_service import (
    create_live_target_db,
    delete_live_target_db,
    get_live_target_db,
    list_live_target_dbs,
)
from src.services.metric_context import (
    MetricContextResult,
    build_data_context,
    fast_metric_context,
)
from src.services.metric_dedupe import load_existing_for_dedupe
from src.services.metric_request_service import (
    MetricRequestError,
    approve_metric_request,
    create_metric_request,
    list_metric_requests,
    list_notifications,
    mark_notification_read,
    mark_notifications_read,
    reject_metric_request,
)
from src.services.metric_rollback import rollback_metric as rollback_metric_record
from src.services.metric_schema_selector import select_metric_schema
from src.services.metric_versioning import latest_open_version
from src.services.metrics import (
    MetricGenerationError,
    MetricGenerationTimeoutError,
    generate_metrics_from_prompt,
    normalize_prompt,
)
from src.services.natural_language_query import (
    build_parser_catalog,
    execute_natural_language_query,
)
from src.services.notification_stream import notification_event_stream
from src.services.organization_service import (
    ROLE_PERMISSIONS,
    get_membership,
    require_permission,
    resolve_membership,
)
from src.services.query_compiler import SemanticQueryCompiler
from src.services.query_execution import execute_compiled_query
from src.services.schema_fingerprint import fast_introspect_schema_fingerprint
from src.services.schema_ingestion import parse_sql_dump_preview
from src.services.schema_review_service import (
    SchemaRowNotFoundError,
    update_column_review,
    update_table_review,
)
from src.services.schema_self_healing_service import execute_self_healing
from src.services.semantic_compile_error import SemanticCompileError
from src.services.semantic_concept_resolver import (
    format_semantic_schema_for_prompt,
    get_reachable_semantic_schema,
)
from src.services.semantic_service import (
    DuplicateMetricError,
    _coerce_metric_definition,
    approve_metric,
    create_metric,
    delete_semantic_database,
    enrich_and_save_canonical_schema,
    get_metric_with_history,
    restore_metric,
    soft_delete_metric,
)
from src.services.semantic_service import (
    update_metric as update_metric_record,
)
from src.services.sql_dump_parser_models import SqlDumpParseError
from src.services.sql_dump_scanner_models import SqlDumpScanError

logger = logging.getLogger(__name__)


async def _execute_sql_on_live_db(
    conn_url: str,
    dialect: str,
    compiled: Any,
) -> dict[str, Any]:
    """Adapt the query execution module to the route response shape."""
    result = await execute_compiled_query(conn_url, dialect, compiled)
    return {"columns": result.columns, "rows": result.rows, "row_count": result.row_count}


router = APIRouter(dependencies=[Depends(get_current_user)])


async def _request_org_id(db: AsyncSession, user_id: int, org_id: int | None) -> int:
    """Resolve the active Workspace for a semantic resource mutation."""
    try:
        organization, _ = await resolve_membership(db, user_id, org_id)
        return organization.id
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _require_org_permission(db: AsyncSession, user_id: int, org_id: int | None, permission: str) -> None:
    """Enforce a Workspace permission for the selected Workspace."""
    try:
        _, membership = await resolve_membership(db, user_id, org_id)
        require_permission(membership, permission)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _require_resource_permission(
    db: AsyncSession,
    user_id: int,
    db_id: int,
    org_id: int | None,
    permission: str,
) -> SemanticDatabaseModel:
    """Authorize a resource and permission in the active Workspace."""
    resource = await db.get(SemanticDatabaseModel, db_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    try:
        organization, membership = await resolve_membership(db, user_id, org_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if resource.org_id is not None and resource.org_id != organization.id:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    if resource.org_id is None and resource.created_by != user_id:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    if resource.org_id is None:
        return resource
    try:
        require_permission(membership, permission)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return resource


DEMO_RETAIL_SCHEMA: dict[str, Any] = {
    "order_header": {
        "business_name": "Đơn hàng",
        "description": "Bảng chứa thông tin tổng quan của đơn hàng",
        "columns": [
            {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "business_name": "Mã đơn hàng"},
            {"column_name": "customer_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã KH"},
            {"column_name": "store_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã cửa hàng"},
            {
                "column_name": "sales_channel_id",
                "data_type": "INTEGER",
                "is_foreign_key": True,
                "business_name": "Kênh bán",
            },
            {
                "column_name": "payment_method_id",
                "data_type": "INTEGER",
                "is_foreign_key": True,
                "business_name": "Phương thức thanh toán",
            },
            {"column_name": "total_amount", "data_type": "NUMERIC", "business_name": "Tổng tiền đơn"},
            {"column_name": "discount_amount", "data_type": "NUMERIC", "business_name": "Tiền giảm giá"},
            {"column_name": "shipping_fee", "data_type": "NUMERIC", "business_name": "Phí vận chuyển"},
            {"column_name": "order_status", "data_type": "VARCHAR(20)", "business_name": "Trạng thái đơn"},
            {"column_name": "created_at", "data_type": "TIMESTAMP", "business_name": "Ngày tạo đơn"},
        ],
    },
    "order_line": {
        "business_name": "Chi tiết đơn hàng",
        "description": "Bảng chứa chi tiết các mặt hàng trong đơn",
        "columns": [
            {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "business_name": "Mã dòng"},
            {"column_name": "order_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã đơn hàng"},
            {"column_name": "product_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã SP"},
            {"column_name": "quantity", "data_type": "INTEGER", "business_name": "Số lượng mua"},
            {"column_name": "unit_price", "data_type": "NUMERIC", "business_name": "Đơn giá"},
            {"column_name": "line_total", "data_type": "NUMERIC", "business_name": "Thành tiền dòng"},
        ],
    },
    "products": {
        "business_name": "Sản phẩm",
        "description": "Bảng danh mục sản phẩm",
        "columns": [
            {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "business_name": "Mã sản phẩm"},
            {"column_name": "product_name", "data_type": "VARCHAR(150)", "business_name": "Tên sản phẩm"},
            {"column_name": "category_id", "data_type": "INTEGER", "business_name": "Danh mục"},
            {"column_name": "cost_price", "data_type": "NUMERIC", "business_name": "Giá vốn"},
            {"column_name": "selling_price", "data_type": "NUMERIC", "business_name": "Giá bán niêm yết"},
            {"column_name": "is_active", "data_type": "BOOLEAN", "business_name": "Đang kinh doanh"},
        ],
    },
}


def _parse_int_id(raw_id: str | int) -> int | None:
    """Safely convert string or int db_id to integer."""
    try:
        return int(raw_id)
    except (ValueError, TypeError):
        return None


def _actor_name(actor: UserModel | None) -> str:
    """Render a display name for a version actor, falling back to their email."""
    if actor is None:
        return ""
    return (getattr(actor, "full_name", "") or "").strip() or getattr(actor, "email", "") or ""


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


# ---------------------------------------------------------------------------
# 1. SQL Dump Ingestion & Technical Preview (Chức năng từ main)
# ---------------------------------------------------------------------------


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


@router.post("/semantic/import/saved", response_model=ImportedSchemaResponse, status_code=201)
async def save_imported_schema(
    body: ImportedSchemaCreateRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ImportedSchemaResponse:
    """Persist parsed schema metadata under a user-provided display name."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    await _require_org_permission(db, current_user.id, active_org_id, "can_manage_schema")
    return await create_imported_schema(db, current_user.id, body.display_name, body.raw_schema, active_org_id)


@router.get("/semantic/import/saved", response_model=list[ImportedSchemaSummaryResponse])
async def get_saved_imported_schemas(
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ImportedSchemaSummaryResponse]:
    """List imported schemas owned by the authenticated user."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    return await list_imported_schemas(db, current_user.id, active_org_id)


@router.get("/semantic/import/saved/{schema_id}", response_model=ImportedSchemaResponse)
async def get_saved_imported_schema(
    schema_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ImportedSchemaResponse:
    """Load one user-owned imported schema for preview."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    record = await get_imported_schema(db, current_user.id, schema_id, active_org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved schema not found")
    return record


@router.delete("/semantic/import/saved/{schema_id}", status_code=204)
async def remove_saved_imported_schema(
    schema_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete one user-owned imported schema."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    await _require_org_permission(db, current_user.id, active_org_id, "can_manage_schema")
    if not await delete_imported_schema(db, current_user.id, schema_id, active_org_id):
        raise HTTPException(status_code=404, detail="Saved schema not found")


# ---------------------------------------------------------------------------
# 2. Live Target Database Management (Chức năng từ main)
# ---------------------------------------------------------------------------


@router.post("/semantic/db/connect", response_model=LiveDbResponse, status_code=201)
async def connect_live_target_db(
    body: LiveDbConnectRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LiveDbResponse:
    """Connect to a live target database, encrypt URL, introspect schema without SELECT data, and persist."""
    logger.info(
        "Received live DB connect request: display_name='%s', dialect=%s, user_id=%d",
        body.display_name,
        body.dialect,
        current_user.id,
    )
    try:
        active_org_id = await _request_org_id(db, current_user.id, org_id)
        await _require_org_permission(db, current_user.id, active_org_id, "can_manage_schema")
        return await create_live_target_db(
            db,
            current_user.id,
            body.display_name,
            body.dialect,
            body.conn_url,
            active_org_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to connect live DB '%s': %s", body.display_name, exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to connect and introspect target database: {exc}") from exc


@router.get("/semantic/db/saved", response_model=list[LiveDbSummaryResponse])
async def get_saved_live_target_dbs(
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[LiveDbSummaryResponse]:
    """List live target databases connected and saved by the user."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    return await list_live_target_dbs(db, current_user.id, active_org_id)


@router.get("/semantic/db/saved/{db_id}", response_model=LiveDbResponse)
async def get_saved_live_target_db(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LiveDbResponse:
    """Get details and raw schema metadata of a saved live target database."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    record = await get_live_target_db(db, current_user.id, db_id, active_org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved live database not found")
    return record


@router.delete("/semantic/db/saved/{db_id}", status_code=204)
async def remove_saved_live_target_db(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a saved live target database connection."""
    active_org_id = await _request_org_id(db, current_user.id, org_id)
    await _require_org_permission(db, current_user.id, active_org_id, "can_manage_schema")
    if not await delete_live_target_db(db, current_user.id, db_id, active_org_id):
        raise HTTPException(status_code=404, detail="Saved live database not found")


@router.delete("/semantic/db/{db_id}", status_code=204)
async def remove_database_unified(
    db_id: str,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a database connection or schema and all associated tables, metrics, and relationships."""
    parsed_id = _parse_int_id(db_id)
    deleted = False
    if parsed_id is not None:
        await _require_resource_permission(db, current_user.id, parsed_id, org_id, "can_manage_schema")
        if await delete_live_target_db(db, current_user.id, parsed_id, org_id):
            deleted = True
        elif await delete_imported_schema(db, current_user.id, parsed_id, org_id):
            deleted = True
        elif await delete_semantic_database(db, parsed_id, current_user.id):
            deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail="Database not found")


# ---------------------------------------------------------------------------
# 3. Flow 1 — Generate & HITL
# ---------------------------------------------------------------------------


@router.post("/semantic/generate", response_model=SemanticGenerateV2Response, status_code=status.HTTP_202_ACCEPTED)
async def generate_semantic_layer(
    request: GenerateRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticGenerateV2Response:
    """Re-run AI Enrichment for an existing semantic database.

    Looks up the source (live DB or imported schema) linked to the semantic db,
    reconstructs the raw schema metadata, and calls enrich_and_save_canonical_schema.
    """
    db_id = request.db_id
    logger.info("Received request to re-generate AI semantic layer for db_id=%d (user_id=%d)", db_id, current_user.id)

    sem_db = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_schema")

    raw_schema, dialect = await _find_source_raw_schema(db, db_id, sem_db.db_type)

    try:
        result = await enrich_and_save_canonical_schema(
            db=db,
            user_id=current_user.id,
            connection_id=db_id,
            raw_schema=raw_schema,
            dialect=dialect,
        )
    except Exception as exc:
        logger.error("Enrichment failed for db_id=%d: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {exc}") from exc

    return SemanticGenerateV2Response(
        db_id=db_id,
        status=result.get("status", "draft"),
        pending_tables=result.get("pending_tables", 0),
        pending_columns=result.get("pending_columns", 0),
        tables=result.get("tables", []),
        relationships=result.get("relationships", []),
    )


async def _find_source_raw_schema(
    db: AsyncSession,
    semantic_db_id: int,
    fallback_dialect: str,
) -> tuple[RawSchemaMetadata, str]:
    """Find the source model (LiveTargetDbModel or ImportedSchemaModel) for a semantic db.

    Returns (raw_schema, dialect) tuple.
    """
    live_stmt = select(LiveTargetDbModel).where(
        (LiveTargetDbModel.semantic_db_id == semantic_db_id) | (LiveTargetDbModel.id == semantic_db_id)
    )
    live_result = await db.execute(live_stmt)
    live_db = live_result.scalar_one_or_none()
    if live_db:
        raw_schema = RawSchemaMetadata.model_validate(live_db.schema_metadata)
        return raw_schema, live_db.dialect

    imported_stmt = select(ImportedSchemaModel).where(
        (ImportedSchemaModel.semantic_db_id == semantic_db_id) | (ImportedSchemaModel.id == semantic_db_id)
    )
    imported_result = await db.execute(imported_stmt)
    imported = imported_result.scalar_one_or_none()
    if imported:
        raw_schema = RawSchemaMetadata.model_validate(imported.schema_metadata)
        return raw_schema, imported.dialect

    raise HTTPException(
        status_code=404,
        detail="No source (live DB or imported schema) found for this semantic database",
    )


@router.post("/semantic/approve", response_model=SemanticApproveV2Response)
async def approve_semantic_layer(
    request: ApproveRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticApproveV2Response:
    """Approve all draft metrics for a semantic database."""
    db_id = request.db_id
    sem_db = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")

    metrics_stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.status.in_(["pending_approval", "unverified"]),
    )
    metrics_result = await db.execute(metrics_stmt)
    draft_metrics = metrics_result.scalars().all()

    if not draft_metrics:
        raise HTTPException(status_code=404, detail="No draft metrics found to approve")

    approved_count = 0
    errors: list[str] = []
    for metric in draft_metrics:
        if sem_db.org_id is None and metric.created_by not in {None, current_user.id}:
            continue
        try:
            await approve_metric(db=db, metric_id=metric.id, user_id=current_user.id)
            approved_count += 1
        except ValueError as exc:
            errors.append(str(exc))

    if approved_count == 0:
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        raise HTTPException(status_code=404, detail="No draft metrics found to approve")

    sem_db.status = "saved"
    await db.commit()

    return SemanticApproveV2Response(
        db_id=db_id,
        approved_count=approved_count,
        message=f"Approved {approved_count} metric(s)",
    )


@router.post("/semantic/{db_id}/metric/{metric_id}/approve", response_model=MetricResponse)
async def approve_single_metric_endpoint(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Approve a single metric by its ID."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")
    stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.is_deleted.is_(False),
    )
    metric = (await db.execute(stmt)).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")

    try:
        approved = await approve_metric(db=db, metric_id=metric_id, user_id=current_user.id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MetricResponse(
        metric_id=approved.id,
        definition=approved.definition,
        source=approved.source or "manual",
        status=approved.status,
        is_deleted=approved.is_deleted,
        name=approved.name,
    )


# ---------------------------------------------------------------------------
# 4. HITL Inline Edit — Tables & Columns (Chức năng từ nhánh của bạn)
# ---------------------------------------------------------------------------


@router.put("/semantic/{db_id}/table/{table_name}", status_code=status.HTTP_200_OK)
async def update_table(
    db_id: str,
    table_name: str,
    body: SemanticTableUpdate,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Apply a reviewer's inline edit to a table, keeping it pending until approval."""
    int_id = _parse_int_id(db_id)
    if int_id is not None:
        await _require_resource_permission(db, user.id, int_id, org_id, "can_manage_schema")
    if int_id is None:
        return {"message": "Table updated successfully"}

    try:
        table = await update_table_review(db, int_id, table_name, body.business_name, body.description, user.id)
    except SchemaRowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found") from exc
    await db.commit()
    return {"message": "Table updated successfully", "review_status": table.review_status}


@router.put("/semantic/{db_id}/column/{table_name}/{column_name}", status_code=status.HTTP_200_OK)
async def update_column(
    db_id: str,
    table_name: str,
    column_name: str,
    body: SemanticColumnUpdate,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Apply a reviewer's inline edit to a column, keeping it pending until approval."""
    int_id = _parse_int_id(db_id)
    if int_id is not None:
        await _require_resource_permission(db, user.id, int_id, org_id, "can_manage_schema")
    if int_id is None:
        return {"message": "Column updated successfully"}

    try:
        column = await update_column_review(
            db, int_id, table_name, column_name, body.business_name, body.description, user.id
        )
    except SchemaRowNotFoundError as exc:
        detail = "Table not found" if "Table" in str(exc) else "Column not found"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    await db.commit()
    return {"message": "Column updated successfully", "review_status": column.review_status}


# ---------------------------------------------------------------------------
# 5. AI Prompt Metric Generation & Metric CRUD (Chức năng từ nhánh của bạn)
# ---------------------------------------------------------------------------


async def _load_schema_context_for_db(db: AsyncSession, db_id: Any) -> dict[str, Any]:
    """Helper to fetch schema context from database with eager loading or fallback to source raw_schema."""
    try:
        numeric_db_id = int(db_id)
        stmt = (
            select(SemanticTableModel)
            .options(selectinload(SemanticTableModel.columns))
            .where(SemanticTableModel.db_id == numeric_db_id)
        )
        res = await db.execute(stmt)
        tables = res.scalars().all()
        if tables:
            schema_dict: dict[str, Any] = {}
            for tbl in tables:
                schema_dict[tbl.table_name] = {
                    "business_name": tbl.business_name or tbl.table_name,
                    "description": tbl.description or "",
                    "columns": [
                        {
                            "column_name": col.column_name,
                            "data_type": col.data_type,
                            "business_name": col.business_name or col.column_name,
                            "is_primary_key": col.is_primary_key,
                            "is_foreign_key": col.is_foreign_key,
                            "is_nullable": col.is_nullable,
                            "fk_target_table": col.fk_target_table,
                            "fk_target_column": col.fk_target_column,
                            "description": col.description or "",
                            "sample_values": col.allowed_values,
                            "allowed_values": col.allowed_values,
                        }
                        for col in tbl.columns
                    ],
                }
            return schema_dict

        # Fallback to source raw_schema if semantic_tables is empty
        try:
            raw_schema_meta, _ = await _find_source_raw_schema(db, numeric_db_id, "postgresql")
            if raw_schema_meta and raw_schema_meta.tables:
                schema_dict: dict[str, Any] = {}
                for tbl in raw_schema_meta.tables:
                    t_name = tbl.table_name.raw_name
                    schema_dict[t_name] = {
                        "business_name": t_name,
                        "description": "",
                        "columns": [
                            {
                                "column_name": col.column_name.raw_name,
                                "data_type": col.data_type,
                                "business_name": col.column_name.raw_name,
                                "is_primary_key": col.primary_key,
                                "is_foreign_key": False,
                                "is_nullable": col.nullable,
                            }
                            for col in tbl.columns
                        ],
                    }
                return schema_dict
        except Exception as exc:
            logger.debug("Schema context fallback failed for db_id=%s: %s", db_id, exc)
    except (ValueError, TypeError) as exc:
        logger.debug("Invalid semantic database id %s: %s", db_id, exc)

    return DEMO_RETAIL_SCHEMA


async def _load_approved_metric_context(db: AsyncSession, db_id: int) -> list[dict[str, Any]]:
    """Return safe approved metric context for the read-only data assistant."""
    stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.status == "approved",
    )
    metrics = (await db.execute(stmt)).scalars().all()
    return [
        {"id": metric.id, "name": metric.name, "definition": _safe_metric_definition(metric.definition)}
        for metric in metrics
    ]


async def _chat_can_generate_metrics(db: AsyncSession, database: SemanticDatabaseModel, user_id: int) -> bool:
    """Resolve metric-authoring capability from Workspace membership.

    The capability is a Data Lead-only capability and is never inferred from
    generic query/chat access. It is sourced from the explicit ``can_generate_metrics``
    permission so the contract stays decoupled from ``can_use_metric_studio``.
    """
    if database.org_id is None:
        return True
    membership = await get_membership(db, user_id, database.org_id)
    return bool(membership and ROLE_PERMISSIONS.get(membership.role, {}).get("can_generate_metrics", False))


async def _chat_role(db: AsyncSession, database: SemanticDatabaseModel, user_id: int) -> str:
    """Resolve the active workspace role used for role-aware chat clarification."""
    if database.org_id is None:
        return "data_lead"
    membership = await get_membership(db, user_id, database.org_id)
    return membership.role if membership else "member"


@router.post("/semantic/{db_id}/metrics/generate", response_model=CustomMetricGenerateResponse)
async def generate_custom_metrics(
    db_id: str,
    body: CustomMetricGenerateRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CustomMetricGenerateResponse:
    """Sinh công thức Business Metrics thông minh từ yêu cầu người dùng bằng tiếng Việt."""
    try:
        clean_prompt = normalize_prompt(body.prompt)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prompt yêu cầu không được để trống hoặc chỉ chứa khoảng trắng.",
        ) from err

    try:
        numeric_db_id = int(db_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=f"Database with id {db_id} not found") from error
    await _require_resource_permission(db, current_user.id, numeric_db_id, org_id, "can_submit_metric")
    context = await fast_metric_context(db, numeric_db_id)
    schema = select_metric_schema(context.schema, clean_prompt, body.target_tables)
    if not schema.get("tables"):
        raise HTTPException(status_code=422, detail="Bảng được chọn không tồn tại trong schema.")

    try:
        existing, dedupe_performed = await load_existing_for_dedupe(db, db_id)
        suggestions, duplicates = await generate_metrics_from_prompt(
            prompt=clean_prompt,
            schema_context=schema,
            target_tables=body.target_tables,
            existing_metrics=existing or None,
        )
        return CustomMetricGenerateResponse(
            suggestions=suggestions,
            duplicates=duplicates,
            dedupe_performed=dedupe_performed,
        )
    except MetricGenerationError as exc:
        raise _metric_generation_http_error(exc) from exc
    except Exception as exc:
        logger.error(f"Lỗi khi sinh metrics từ prompt: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể sinh metrics từ AI Service: {exc}",
        ) from exc


def _metric_generation_http_error(error: MetricGenerationError) -> HTTPException:
    """Map bounded Metric LLM failures to stable upstream HTTP semantics."""
    if isinstance(error, MetricGenerationTimeoutError):
        return HTTPException(status_code=504, detail="AI phản hồi quá 45 giây. Vui lòng thử lại.")
    return HTTPException(status_code=502, detail="AI trả về Metric Definition không hợp lệ.")


@router.post("/semantic/{db_id}/metric", response_model=MetricResponse, status_code=201)
async def create_metric_endpoint(
    db_id: int,
    body: MetricCreate,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Tạo Business Metric mới — tự động tạo record trong metric_versions."""
    db_record = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_submit_metric")
    membership = await get_membership(db, current_user.id, db_record.org_id) if db_record.org_id is not None else None

    metric_data: dict[str, Any] = {
        "definition": body.definition.model_dump(mode="json"),
        "source": body.source,
    }

    try:
        new_metric = await create_metric(
            db=db,
            connection_id=db_id,
            metric_data=metric_data,
            user_id=current_user.id,
            status_override="unverified" if membership and membership.role == "member" else None,
        )
    except DuplicateMetricError as exc:
        logger.info("Duplicate metric rejected for db_id=%s: %s", db_id, exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("create_metric validation error for db_id=%s: %s", db_id, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Update DB status to 'draft' after metric creation
    db_record.status = "draft"
    await db.commit()

    return MetricResponse(
        metric_id=new_metric.id,
        definition=new_metric.definition,
        source=new_metric.source or "manual",
        status=new_metric.status,
        is_deleted=new_metric.is_deleted,
        name=new_metric.name,
    )


@router.post("/semantic/{db_id}/metric-requests", response_model=MetricRequestResponse, status_code=201)
async def submit_metric_request(
    db_id: int,
    body: MetricRequestCreate,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricRequestResponse:
    """Submit one server-verified AI suggestion for Data Lead review."""
    database = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_submit_metric")
    if await _chat_can_generate_metrics(db, database, current_user.id):
        raise HTTPException(status_code=403, detail="Data Leads should save metrics directly")
    try:
        request = await create_metric_request(
            db, db_id, current_user.id, body.assistant_message_id, body.suggestion_index
        )
    except (MetricRequestError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MetricRequestResponse.model_validate(request)


@router.get("/semantic/{db_id}/metric-requests", response_model=list[MetricRequestResponse])
async def get_metric_requests(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[MetricRequestResponse]:
    """List pending and resolved requests visible to the active role."""
    database = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_use_data_assistant")
    is_lead = await _chat_can_generate_metrics(db, database, current_user.id)
    requests = await list_metric_requests(db, db_id, current_user.id, is_lead)
    return [MetricRequestResponse.model_validate(item) for item in requests]


@router.post("/semantic/{db_id}/metric-requests/{request_id}/approve", response_model=MetricRequestResponse)
async def accept_metric_request(
    db_id: int,
    request_id: int,
    body: MetricRequestReview,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricRequestResponse:
    """Create and approve the reviewed metric in a single transaction."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")
    request = await db.get(MetricRequestModel, request_id)
    if request is None or request.db_id != db_id:
        raise HTTPException(status_code=404, detail="Metric request not found")
    try:
        reviewed = await approve_metric_request(db, request_id, current_user.id, body.definition, body.review_note)
    except (MetricRequestError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MetricRequestResponse.model_validate(reviewed)


@router.post("/semantic/{db_id}/metric-requests/{request_id}/reject", response_model=MetricRequestResponse)
async def decline_metric_request(
    db_id: int,
    request_id: int,
    body: MetricRequestReview,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricRequestResponse:
    """Reject a pending metric request and notify its requester."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_approve_metrics")
    request = await db.get(MetricRequestModel, request_id)
    if request is None or request.db_id != db_id:
        raise HTTPException(status_code=404, detail="Metric request not found")
    try:
        reviewed = await reject_metric_request(db, request_id, current_user.id, body.review_note)
    except MetricRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MetricRequestResponse.model_validate(reviewed)


def _safe_metric_definition(definition_raw: Any) -> MetricDefinition | None:
    if not definition_raw or not isinstance(definition_raw, dict):
        return None
    try:
        return MetricDefinition.model_validate(definition_raw)
    except Exception:
        try:
            return MetricDefinition.model_validate(_coerce_metric_definition(definition_raw))
        except Exception:
            return None


@router.get("/semantic/{db_id}/metrics", response_model=list[MetricListItem])
async def list_metrics(
    db_id: int,
    include_deleted: bool = Query(default=False),
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[MetricListItem]:
    """Danh sách metrics kèm version, status, approved_by."""
    semantic_db = await _owned_semantic_database(db, db_id, current_user.id, org_id)
    if semantic_db is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.db_id == db_id).order_by(SemanticMetricModel.id)
    if not include_deleted:
        stmt = stmt.where(SemanticMetricModel.is_deleted.is_(False))
    if semantic_db.org_id is not None:
        _, membership = await resolve_membership(db, current_user.id, org_id)
        if membership and membership.role == "admin":
            stmt = stmt.where(SemanticMetricModel.status == "approved")
        elif membership and membership.role == "member":
            stmt = stmt.where(
                (SemanticMetricModel.status == "approved")
                | ((SemanticMetricModel.status == "unverified") & (SemanticMetricModel.created_by == current_user.id))
            )
    result = await db.execute(stmt)
    metrics = result.scalars().all()

    # Query open pending versions across metrics for this database
    v_stmt = (
        select(MetricVersionModel.metric_id, func.max(MetricVersionModel.version))
        .where(
            MetricVersionModel.metric_id.in_([m.id for m in metrics]) if metrics else False,
            MetricVersionModel.status.in_({"pending_approval", "needs_review"}),
        )
        .group_by(MetricVersionModel.metric_id)
    )
    v_map: dict[int, int] = {}
    if metrics:
        v_rows = (await db.execute(v_stmt)).all()
        v_map = {row[0]: row[1] for row in v_rows}

    return [
        MetricListItem(
            metric_id=m.id,
            name=m.name,
            definition=_safe_metric_definition(m.definition),
            source=m.source or "manual",
            version=m.version or 1,
            status=m.status or "needs_review",
            is_deleted=m.is_deleted,
            approved_by=m.approved_by,
            created_at=m.created_at,
            has_pending_version=m.id in v_map,
            pending_version_number=v_map.get(m.id),
        )
        for m in metrics
    ]


@router.get("/semantic/{db_id}/catalog", response_model=SemanticCatalogResponse)
async def get_semantic_catalog(
    db_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticCatalogResponse:
    """Return canonical IDs and query capability for an owned semantic database."""
    semantic_db = await _owned_semantic_database(db, db_id, current_user.id, org_id)
    if semantic_db is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    source_type = await _catalog_source_type(db, db_id)
    return SemanticCatalogResponse(
        db_id=db_id,
        source_type=source_type,
        query_supported=source_type == "live",
        tables=await _catalog_tables(db, db_id),
        relationships=await _catalog_relationships(db, db_id),
    )


async def _owned_semantic_database(
    db: AsyncSession, db_id: int, user_id: int, org_id: int | None = None
) -> SemanticDatabaseModel | None:
    """Find a semantic database owned by or shared with the authenticated user."""
    try:
        organization, _ = await resolve_membership(db, user_id, org_id)
    except (PermissionError, ValueError):
        return None
    stmt = (
        select(SemanticDatabaseModel)
        .outerjoin(OrganizationMemberModel, OrganizationMemberModel.org_id == SemanticDatabaseModel.org_id)
        .where(
            SemanticDatabaseModel.id == db_id,
            ((SemanticDatabaseModel.org_id == organization.id) & (OrganizationMemberModel.user_id == user_id))
            | ((SemanticDatabaseModel.org_id.is_(None)) & (SemanticDatabaseModel.created_by == user_id)),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _metric_is_visible(metric: SemanticMetricModel, role: str, user_id: int) -> bool:
    """Apply approved, Data Lead, or own-unverified metric visibility."""
    return bool(
        metric.status == "approved"
        or role == "data_lead"
        or (role == "member" and metric.status == "unverified" and metric.created_by == user_id)
    )


async def _visible_metric(
    db: AsyncSession,
    db_id: int,
    metric_id: int,
    user_id: int,
    org_id: int | None,
    allow_deleted: bool = False,
) -> SemanticMetricModel:
    """Authorize a metric's database and lifecycle visibility."""
    semantic_db = await _owned_semantic_database(db, db_id, user_id, org_id)
    if semantic_db is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    metric = await db.scalar(
        select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id, SemanticMetricModel.db_id == db_id)
    )
    if metric is None or (metric.is_deleted and not allow_deleted):
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")
    if semantic_db.org_id is not None:
        membership = await get_membership(db, user_id, semantic_db.org_id)
        if membership is None or not _metric_is_visible(metric, membership.role, user_id):
            raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")
    return metric


async def _catalog_tables(db: AsyncSession, db_id: int) -> list[SemanticCatalogTable]:
    """Load canonical tables and columns for the query builder."""
    stmt = (
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
        .options(selectinload(SemanticTableModel.columns))
        .order_by(SemanticTableModel.id)
    )
    tables = (await db.execute(stmt)).scalars().all()
    return [_catalog_table(table) for table in tables]


def _catalog_table(table: SemanticTableModel) -> SemanticCatalogTable:
    """Map a canonical table model to its public catalog representation."""
    columns = [
        SemanticCatalogColumn(
            column_id=column.id,
            column_name=column.column_name,
            business_name=column.business_name,
            data_type=column.data_type,
            is_time_dimension=column.is_time_dimension,
            is_primary_key=column.is_primary_key,
            is_foreign_key=column.is_foreign_key,
            allowed_values=column.allowed_values,
        )
        for column in sorted(table.columns, key=lambda item: item.id)
    ]
    return SemanticCatalogTable(
        table_id=table.id,
        table_name=table.table_name,
        business_name=table.business_name,
        columns=columns,
    )


def _catalog_relationship(rel: CanonicalRelationshipModel) -> CanonicalRelationshipResponse:
    """Map a canonical relationship model to its public catalog representation."""
    return CanonicalRelationshipResponse(
        id=rel.id,
        connection_id=rel.connection_id,
        from_entity_id=rel.from_entity_id,
        to_entity_id=rel.to_entity_id,
        relationship_type=rel.relationship_type,
        join_condition=rel.join_condition,
        business_name=rel.business_name,
        description=rel.description,
        validation_status=rel.validation_status,
        review_status=rel.review_status,
        created_at=rel.created_at,
    )


async def _catalog_relationships(db: AsyncSession, db_id: int) -> list[CanonicalRelationshipResponse]:
    """Load only valid, human-approved canonical relationships for a semantic database.

    Flow 2 consumers must never receive pending or technically invalid
    relationships, so the query filters on both governance signals.
    """
    stmt = (
        select(CanonicalRelationshipModel)
        .where(
            CanonicalRelationshipModel.connection_id == db_id,
            CanonicalRelationshipModel.review_status == REVIEW_STATUS_APPROVED,
            CanonicalRelationshipModel.validation_status == "valid",
        )
        .order_by(CanonicalRelationshipModel.id)
    )
    records = (await db.execute(stmt)).scalars().all()
    return [_catalog_relationship(rel) for rel in records]


async def _catalog_source_type(db: AsyncSession, db_id: int) -> str:
    """Identify whether a semantic database is backed by a live connection."""
    stmt = select(LiveTargetDbModel.id).where(LiveTargetDbModel.semantic_db_id == db_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        return "live"
    return "sql_dump"


@router.get("/semantic/{db_id}/metric/{metric_id}/history", response_model=MetricHistoryResponse)
async def get_metric_history(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricHistoryResponse:
    """Lịch sử version của một metric."""
    await _visible_metric(db, db_id, metric_id, current_user.id, org_id, allow_deleted=True)
    metric = await get_metric_with_history(db=db, metric_id=metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")

    versions = [
        MetricVersionItem(
            version=v.version,
            definition=v.definition,
            changed_by=v.changed_by,
            changed_by_name=_actor_name(v.changer),
            change_reason=v.change_reason or "",
            status=v.status,
            parent_version=v.parent_version,
            approved_by=v.approved_by,
            approved_by_name=_actor_name(v.approver),
            approved_at=v.approved_at,
            created_at=v.created_at,
        )
        for v in sorted(metric.versions, key=lambda x: x.version)
    ]

    return MetricHistoryResponse(
        metric_id=metric.id,
        metric_name=metric.name,
        live_version=metric.version,
        versions=versions,
    )


@router.get("/semantic/{db_id}/metric/{metric_id}/dimensions", response_model=MetricDimensionsResponse)
async def get_metric_recommended_dimensions(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
) -> MetricDimensionsResponse:
    """Recommend high-signal dimensions for a specific metric across Tier A, B, C, and D."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_query")
    stmt_metric = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
    )
    metric = (await db.execute(stmt_metric)).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Metric {metric_id} not found")

    if metric.status == "unverified" and metric.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Metric {metric_id} not found")

    base_table_name = ""
    if metric.base_entity_id:
        stmt_t = select(SemanticTableModel.table_name).where(SemanticTableModel.id == metric.base_entity_id)
        base_table_name = (await db.execute(stmt_t)).scalar_one_or_none() or ""

    dims = await get_dimensions_for_metric(db, db_id, metric_id)
    return MetricDimensionsResponse(
        metric_id=metric.id,
        metric_name=metric.name,
        base_table=base_table_name,
        dimensions=dims,
    )


@router.get("/semantic/{db_id}/metric/{metric_id}/filter-columns", response_model=MetricFilterColumnsResponse)
async def get_metric_filter_columns(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
) -> MetricFilterColumnsResponse:
    """Retrieve safe and relevant filter columns for a specific metric."""
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_query")
    stmt_metric = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
    )
    metric = (await db.execute(stmt_metric)).scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Metric {metric_id} not found")

    if metric.status == "unverified" and metric.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Metric {metric_id} not found")

    base_table_name = ""
    if metric.base_entity_id:
        stmt_t = select(SemanticTableModel.table_name).where(SemanticTableModel.id == metric.base_entity_id)
        base_table_name = (await db.execute(stmt_t)).scalar_one_or_none() or ""

    cols = await get_filter_columns_for_metric(db, db_id, metric_id)
    return MetricFilterColumnsResponse(
        metric_id=metric.id,
        metric_name=metric.name,
        base_table=base_table_name,
        columns=cols,
    )


@router.get(
    "/semantic/{db_id}/metric/join-path-options",
    response_model=dict[str, list[JoinPathOption]],
)
async def get_metric_join_path_options(
    db_id: int,
    base_entity_id: int = Query(..., description="Base entity id to enumerate join paths from"),
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, list[JoinPathOption]]:
    """List governed, safe join-path options for every entity reachable from a base.

    Only relationships that are technically valid and human-approved are traversed,
    so the options are exactly the paths a metric may persist as a preferred path.
    """
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_submit_metric")
    stmt_rels = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
    relationships = (await db.execute(stmt_rels)).scalars().all()
    options = join_path_options(list(relationships), base_entity_id)
    return {str(target_id): [JoinPathOption(**option) for option in opts] for target_id, opts in options.items()}


async def _metric_update_response(db: AsyncSession, metric: SemanticMetricModel) -> MetricUpdateResponse:
    """Return the live metric plus the copy-on-write draft, if the edit was queued."""
    draft = await latest_open_version(db, metric.id)
    return MetricUpdateResponse(
        metric_id=metric.id,
        definition=metric.definition,
        source=metric.source,
        status=metric.status,
        name=metric.name,
        version=metric.version,
        pending_version=(
            MetricVersionResponse.model_validate(draft, from_attributes=True) if draft is not None else None
        ),
    )


@router.put("/semantic/{db_id}/metric/{metric_id}", response_model=MetricUpdateResponse)
async def update_metric(
    db_id: int,
    metric_id: int,
    body: MetricUpdate,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricUpdateResponse:
    """Replace a metric definition, or park it as a draft when already published."""
    try:
        resource = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_metrics")
        scoped_stmt = select(SemanticMetricModel.id).where(
            SemanticMetricModel.id == metric_id,
            SemanticMetricModel.db_id == db_id,
            SemanticMetricModel.is_deleted.is_(False),
        )
        if (await db.execute(scoped_stmt)).scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")
        metric = await update_metric_record(
            db,
            metric_id,
            {
                "definition": body.definition.model_dump(mode="json"),
                "change_reason": body.change_reason,
            },
            current_user.id,
            require_ownership=resource.org_id is None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(metric)
    return await _metric_update_response(db, metric)


@router.post("/semantic/{db_id}/metric/{metric_id}/rollback/{target_version}", response_model=MetricResponse)
async def rollback_metric(
    db_id: int,
    metric_id: int,
    target_version: int = Path(..., ge=1),
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Destructively rewind a metric to an earlier version and re-approve it."""
    try:
        resource = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_metrics")
        scoped_stmt = select(SemanticMetricModel.id).where(
            SemanticMetricModel.id == metric_id,
            SemanticMetricModel.db_id == db_id,
            SemanticMetricModel.is_deleted.is_(False),
        )
        if (await db.execute(scoped_stmt)).scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")
        metric = await rollback_metric_record(
            db,
            metric_id=metric_id,
            target_version=target_version,
            actor_id=current_user.id,
            require_ownership=resource.org_id is None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(metric)
    return MetricResponse(
        metric_id=metric.id,
        definition=metric.definition,
        source=metric.source,
        status=metric.status,
        is_deleted=metric.is_deleted,
        name=metric.name,
    )


@router.delete("/semantic/{db_id}/metric/{metric_id}", status_code=204)
async def delete_metric(
    db_id: int,
    metric_id: int,
    permanent: bool = Query(default=False),
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Soft-delete hoặc Hard-delete vĩnh viễn một Business Metric khỏi Semantic Layer."""
    resource = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_metrics")
    if permanent:
        scoped_stmt = select(SemanticMetricModel).where(
            SemanticMetricModel.id == metric_id,
            SemanticMetricModel.db_id == db_id,
        )
        metric = (await db.execute(scoped_stmt)).scalar_one_or_none()
        if not metric:
            raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")
        await db.delete(metric)
        await db.commit()
        return

    scoped_stmt = select(SemanticMetricModel.id).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.is_deleted.is_(False),
    )
    if (await db.execute(scoped_stmt)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")
    await soft_delete_metric(
        db,
        metric_id=metric_id,
        user_id=current_user.id,
        require_ownership=resource.org_id is None,
    )
    await db.commit()


@router.post("/semantic/{db_id}/metric/{metric_id}/restore", response_model=MetricResponse)
async def restore_metric_endpoint(
    db_id: int,
    metric_id: int,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Khôi phục một Business Metric đã bị soft-deleted."""
    resource = await _require_resource_permission(db, current_user.id, db_id, org_id, "can_manage_metrics")
    scoped_stmt = select(SemanticMetricModel.id).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == db_id,
    )
    if (await db.execute(scoped_stmt)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")
    metric = await restore_metric(
        db,
        metric_id=metric_id,
        user_id=current_user.id,
        require_ownership=resource.org_id is None,
    )
    await db.commit()
    await db.refresh(metric)
    return MetricResponse(
        metric_id=metric.id,
        definition=_safe_metric_definition(metric.definition),
        source=metric.source or "manual",
        status=metric.status,
        is_deleted=metric.is_deleted,
        name=metric.name,
    )


# ---------------------------------------------------------------------------
# 6. Export (Chức năng chung)
# ---------------------------------------------------------------------------


@router.get("/semantic/{db_id}/export")
async def export_semantic_layer(
    db_id: int,
    format: str = "json",
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """Export approved Semantic Layer as JSON or YAML file download."""
    if format not in ("json", "yaml"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'yaml'")
    await _require_resource_permission(db, current_user.id, db_id, org_id, "can_export")

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
# 7. Semantic Query Execution (Flow 2 — Live DB Only)
# ---------------------------------------------------------------------------


async def _query_target(
    db: AsyncSession,
    db_id: int,
    user_id: int,
    org_id: int | None = None,
    check_drift: bool = False,
) -> tuple[SemanticDatabaseModel, LiveTargetDbModel]:
    semantic_db = await _owned_semantic_database(db, db_id, user_id, org_id)
    if semantic_db is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")

    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    live_db = (await db.execute(live_stmt)).scalar_one_or_none()
    if live_db is None:
        raise HTTPException(status_code=400, detail="Query only supported for Live DB connections")

    if check_drift:
        try:
            conn_url = decrypt_conn_url(live_db.conn_url_enc)
            current_fp = await asyncio.to_thread(fast_introspect_schema_fingerprint, conn_url, live_db.dialect)
            if semantic_db.schema_fingerprint and current_fp != semantic_db.schema_fingerprint:
                logger.info("Schema drift detected before query on db_id=%d. Triggering self-healing...", db_id)
                await execute_self_healing(db, db_id, trigger_type="instant_check")
        except Exception as exc:
            logger.warning("Instant drift check skipped for db_id=%d: %s", db_id, exc)

    return semantic_db, live_db


async def _compile_request(
    db: AsyncSession,
    db_id: int,
    body: SemanticQueryRequest,
) -> Any:
    try:
        return await SemanticQueryCompiler(db).compile(db_id, body.to_spec())
    except SemanticCompileError as exc:
        raise HTTPException(status_code=400, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/semantic/{db_id}/query/compile",
    response_model=SemanticQueryCompileResponse,
)
async def compile_semantic_query(
    db_id: int,
    body: SemanticQueryRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticQueryCompileResponse:
    """Compile a semantic query preview without connecting to the target database."""
    await _query_target(db, db_id, current_user.id, org_id, check_drift=False)
    compiled = await _compile_request(db, db_id, body)
    return SemanticQueryCompileResponse(
        sql=compiled.sql,
        parameters=compiled.parameters,
        metadata=compiled.metadata,
    )


@router.post("/semantic/{db_id}/query", response_model=SemanticQueryResponse)
async def execute_semantic_query(
    db_id: str,
    body: SemanticQueryRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticQueryResponse:
    """Execute a semantic query (Flow 2 — Live DB Only).

    Compiles metric/dimension selections into SQL via SemanticQueryCompiler,
    then executes read-only on the linked Live DB with guardrails.
    """
    parsed_id = _parse_int_id(db_id)
    if parsed_id is None:
        raise HTTPException(status_code=400, detail="Invalid database id")

    _, live_db = await _query_target(db, parsed_id, current_user.id, org_id, check_drift=True)

    compiled = await _compile_request(db, parsed_id, body)

    # Execute on live DB
    try:
        conn_url = decrypt_conn_url(live_db.conn_url_enc)
        exec_result = await _execute_sql_on_live_db(conn_url, live_db.dialect, compiled)
        return SemanticQueryResponse(
            sql=compiled.sql,
            parameters=compiled.parameters,
            columns=exec_result["columns"],
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Query execution timed out") from exc
    except Exception as exc:
        logger.exception("Query execution failed for db_id=%s", db_id)
        raise HTTPException(status_code=500, detail="Query execution failed") from exc


# ---------------------------------------------------------------------------
# 8. Health / Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def agent_status() -> dict:
    """Check agent readiness."""
    return {"status": "ready", "pipeline": "Flow 1 — Generate & Manage Semantic Layer"}


# ---------------------------------------------------------------------------
# 9. AI Chat Orchestrator (Multi-Agent)
# ---------------------------------------------------------------------------


def _chat_db_id(raw_db_id: str) -> int:
    """Parse a semantic database id for chat endpoints."""
    try:
        return int(raw_db_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chat database not found") from exc


def _session_summary(session: ChatSessionModel) -> ChatSessionSummaryResponse:
    """Serialize a chat session summary without exposing sensitive data."""
    return ChatSessionSummaryResponse(
        id=session.id,
        db_id=session.db_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages) if "messages" in session.__dict__ else 0,
    )


def _message_response(message: ChatMessageModel) -> ChatMessageResponse:
    """Serialize one persisted chat message."""
    return ChatMessageResponse.model_validate(message)


def _assistant_metadata(
    suggestions: list[Any] | None = None,
    action: str | None = None,
    duplicates: list[Any] | None = None,
    dedupe_performed: bool = True,
    status_name: str = "completed",
    diagnostics: dict[str, Any] | None = None,
    semantic_query_result: dict[str, Any] | None = None,
    clarification: dict[str, Any] | None = None,
    interpretation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the versioned assistant message metadata contract."""
    return {
        "schema_version": 2,
        "status": status_name,
        "suggestions": suggestions or [],
        "suggestion_action": action,
        "duplicates": duplicates or [],
        "dedupe_performed": dedupe_performed,
        "diagnostics": diagnostics,
        "semantic_query_result": semantic_query_result,
        "clarification": clarification,
        "interpretation": interpretation,
        "error": None,
    }


@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
    current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> NotificationListResponse:
    """Return the current user's persistent in-app notifications."""
    items, unread_count = await list_notifications(db, current_user.id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(item) for item in items], unread_count=unread_count
    )


@router.post("/notifications/read", status_code=204)
async def read_notifications(
    current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> None:
    """Mark all in-app notifications as read for the current user."""
    await mark_notifications_read(db, current_user.id)


@router.post("/notifications/{notification_id}/read", status_code=204)
async def read_notification(
    notification_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Mark one in-app notification as read for the current user."""
    notification = await mark_notification_read(db, current_user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.get("/notifications/stream")
async def stream_notifications(
    current_user: UserModel = Depends(get_current_user),
) -> StreamingResponse:
    """Stream the caller's notification snapshots over server-sent events."""
    return StreamingResponse(
        notification_event_stream(current_user.id, get_session_factory()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/semantic/{db_id}/chat/sessions", response_model=list[ChatSessionSummaryResponse])
async def get_chat_sessions(
    db_id: str,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ChatSessionSummaryResponse]:
    """List chat sessions owned by the current user for one live database."""
    try:
        sessions = await list_chat_sessions(db, current_user.id, _chat_db_id(db_id), org_id=org_id)
    except ChatAuthorizationError as exc:
        raise HTTPException(status_code=404, detail="Chat database not found") from exc
    return [_session_summary(session) for session in sessions]


@router.post("/semantic/{db_id}/chat/sessions", status_code=400)
async def create_chat_session_route() -> None:
    """Reject empty session creation; a session starts with its first query."""
    raise HTTPException(
        status_code=400,
        detail="Query is required to create a conversation.",
    )


@router.get("/semantic/{db_id}/chat/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session_route(
    db_id: str,
    session_id: str,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    limit: int = Query(default=50, ge=1, le=100),
    before_sequence: int | None = Query(default=None, ge=1),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChatSessionDetailResponse:
    """Return one authorized page of chat history."""
    try:
        numeric_db_id = _chat_db_id(db_id)
        await get_chat_database(db, current_user.id, numeric_db_id, org_id=org_id)
        session = await get_chat_session(db, session_id, current_user.id)
        if session is None or session.db_id != numeric_db_id:
            raise ChatAuthorizationError("Chat session not found")
        messages, total, next_cursor = await get_chat_messages_page(
            db, session_id, current_user.id, limit, before_sequence
        )
    except ChatAuthorizationError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    summary = _session_summary(session)
    return ChatSessionDetailResponse(
        id=summary.id,
        db_id=summary.db_id,
        title=summary.title,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        messages=[_message_response(item) for item in messages],
        message_count=total,
        next_before_sequence=next_cursor,
    )


@router.patch("/semantic/{db_id}/chat/sessions/{session_id}", response_model=ChatSessionSummaryResponse)
async def rename_chat_session(
    db_id: str,
    session_id: str,
    body: ChatSessionUpdateRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChatSessionSummaryResponse:
    """Rename one authorized chat session."""
    try:
        numeric_db_id = _chat_db_id(db_id)
        await get_chat_database(db, current_user.id, numeric_db_id, org_id=org_id)
        existing = await get_chat_session(db, session_id, current_user.id)
        if existing is None or existing.db_id != numeric_db_id:
            raise ChatAuthorizationError("Chat session not found")
        session = await update_chat_session_title(db, session_id, current_user.id, body.title)
    except (ChatAuthorizationError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    assert session is not None
    return _session_summary(session)


@router.delete("/semantic/{db_id}/chat/sessions/{session_id}", status_code=204)
async def remove_chat_session(
    db_id: str,
    session_id: str,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete one authorized chat session and its messages."""
    try:
        numeric_db_id = _chat_db_id(db_id)
        await get_chat_database(db, current_user.id, numeric_db_id, org_id=org_id)
        existing = await get_chat_session(db, session_id, current_user.id)
        if existing is None or existing.db_id != numeric_db_id:
            raise ChatAuthorizationError("Chat session not found")
        deleted = await delete_chat_session(db, session_id, current_user.id)
    except ChatAuthorizationError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")


@router.post("/semantic/{db_id}/chat", response_model=ChatResponse)
async def chat_orchestrator(
    db_id: str,
    body: ChatRequest,
    org_id: int | None = Header(default=None, alias="X-Organization-ID"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """Route read-only data assistance, live semantic querying, or metric generation."""
    numeric_db_id = _chat_db_id(db_id)
    try:
        chat_database = await get_chat_database(db, current_user.id, numeric_db_id, org_id=org_id)
        can_generate_metrics = await _chat_can_generate_metrics(db, chat_database, current_user.id)
        session = await _resolve_chat_session(db, body.session_id, current_user.id, numeric_db_id)
        replay = await _replay_chat_response(db, session, current_user.id, body.client_message_id, can_generate_metrics)
        if replay is not None:
            return replay
        if body.clarification_selection:
            return await _handle_clarification_selection(
                db,
                session,
                current_user,
                numeric_db_id,
                body.clarification_selection,
                body,
                can_generate_metrics,
                org_id,
            )
        return await _process_standard_chat(
            db, session, current_user, numeric_db_id, body, can_generate_metrics, org_id, chat_database
        )
    except ChatAuthorizationError as exc:
        raise HTTPException(status_code=404, detail="Chat session or database not found") from exc
    except ClarificationAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail="clarification_already_resolved") from exc


def _resolution_payload(clar_meta: dict) -> ClarificationResolution:
    """Build the canonical resolution object returned to the frontend."""
    if clar_meta.get("resolution_kind") == "skip":
        return ClarificationResolution(status="skipped")
    return ClarificationResolution(
        status="answered",
        selected_option_id=clar_meta.get("selected_option_id"),
        selected_label=clar_meta.get("selected_label"),
        custom_answer=clar_meta.get("custom_answer"),
    )


async def _handle_clarification_selection(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    resolution: ChatClarificationSelection,
    body: ChatRequest,
    can_generate_metrics: bool,
    org_id: int | None = None,
) -> ChatResponse:
    """Route a clarification resolution to the skip/custom/option handlers."""
    prev_msg = await get_chat_message(db, session.id, resolution.assistant_message_id)
    if not prev_msg or not isinstance(prev_msg.metadata_json, dict):
        raise HTTPException(status_code=400, detail="Clarification message not found")
    clar_meta = prev_msg.metadata_json.get("clarification") or {}
    options = clar_meta.get("options", [])
    prompt = clar_meta.get("prompt", "")
    if resolution.skipped:
        return await _resolve_skip_clarification(db, session, current_user, prev_msg, resolution)
    if resolution.custom_answer:
        return await _resolve_custom_clarification(
            db, session, current_user, numeric_db_id, prev_msg, resolution, prompt, body, can_generate_metrics, org_id
        )
    return await _resolve_option_clarification(
        db,
        session,
        current_user,
        numeric_db_id,
        prev_msg,
        resolution,
        options,
        prompt,
        body,
        can_generate_metrics,
        org_id,
    )


async def _resolve_skip_clarification(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    prev_msg: ChatMessageModel,
    resolution: ChatClarificationSelection,
) -> ChatResponse:
    """Persist a skip resolution and return without a user bubble or continuation."""
    resolved = await resolve_clarification_message(
        db, session.id, current_user.id, prev_msg.id, resolution, "Đã bỏ qua"
    )
    refreshed = await get_chat_session_with_messages(db, session.id, current_user.id)
    return ChatResponse(
        intent="clarification_skipped",
        chat_response="Đã bỏ qua",
        session_id=session.id,
        assistant_message_id=prev_msg.id,
        clarification_resolution=_resolution_payload(resolved.metadata_json["clarification"]),
        session=_session_summary(refreshed),
    )


async def _resolve_custom_clarification(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    prev_msg: ChatMessageModel,
    resolution: ChatClarificationSelection,
    prompt: str,
    body: ChatRequest,
    can_generate_metrics: bool,
    org_id: int | None = None,
) -> ChatResponse:
    """Persist a custom answer as exactly one user bubble, then continue analysis."""
    custom_text = resolution.custom_answer.strip()
    client_id = body.client_message_id or f"clarify-custom-{uuid.uuid4()}"
    resolved = await resolve_clarification_message(
        db, session.id, current_user.id, prev_msg.id, resolution, custom_text
    )
    user_msg = await save_chat_message(
        db,
        session.id,
        "user",
        custom_text,
        client_message_id=client_id,
        metadata_json={"clarification_response_to": prev_msg.id},
    )
    analysis_message = f"{prompt}\n{custom_text}" if prompt else custom_text
    body_copy = body.model_copy(
        update={"message": analysis_message, "clarification_selection": None, "client_message_id": client_id}
    )
    response = await _process_standard_chat(
        db, session, current_user, numeric_db_id, body_copy, can_generate_metrics, org_id, save_user_msg=False
    )
    response.user_message_id = user_msg.id
    response.clarification_resolution = _resolution_payload(resolved.metadata_json["clarification"])
    return response


async def _resolve_option_clarification(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    prev_msg: ChatMessageModel,
    resolution: ChatClarificationSelection,
    options: list[dict],
    prompt: str,
    body: ChatRequest,
    can_generate_metrics: bool,
    org_id: int | None = None,
) -> ChatResponse:
    """Resolve an option in place; no user bubble, resolution metadata is sufficient."""
    matched_option = next((opt for opt in options if opt.get("id") == resolution.option_id), None)
    if not matched_option:
        raise HTTPException(status_code=400, detail="Invalid clarification option")
    selected_label = matched_option.get("label", "")
    resolution_payload = None
    try:
        resolved = await resolve_clarification_message(
            db, session.id, current_user.id, prev_msg.id, resolution, selected_label
        )
        resolution_payload = _resolution_payload(resolved.metadata_json["clarification"])
    except ChatAuthorizationError:
        pass

    opt_dims: list[str] = []
    if isinstance(matched_option.get("spec"), dict):
        raw_dims = matched_option.get("spec", {}).get("dimensions", [])
        if isinstance(raw_dims, list):
            opt_dims = [str(d) for d in raw_dims if d]
    elif isinstance(matched_option.get("dimensions"), list):
        opt_dims = [str(d) for d in matched_option["dimensions"] if d]
    if not opt_dims and "gắn chiều" in selected_label.lower():
        part = selected_label.lower().split("gắn chiều")[-1]
        opt_dims = [d.strip() for d in re.split(r"[,&và]", part) if d.strip()]
    clar_meta = prev_msg.metadata_json.get("clarification") if isinstance(prev_msg.metadata_json, dict) else {}
    target_metric_name = clar_meta.get("target_metric_name") if isinstance(clar_meta, dict) else None
    if not target_metric_name and prompt:
        match = re.search(r"tạo chỉ số ['\"‘“](.*?)['\"’”]", prompt, re.IGNORECASE)
        if match:
            target_metric_name = match.group(1).strip()

    dims_suffix = f" với các chiều phân tích: {', '.join(opt_dims)}" if opt_dims else ""
    if target_metric_name:
        analysis_message = (
            f"Tạo chỉ số '{target_metric_name}' theo tiêu chí đã chọn: {selected_label}. "
            f"Chi tiết logic: {matched_option.get('description', '')}{dims_suffix}"
        )
    else:
        analysis_message = (
            f"Tạo metric dựa trên lựa chọn đã làm rõ: {selected_label}. "
            f"Chi tiết: {matched_option.get('description', '')}{dims_suffix}"
        )
    body_copy = body.model_copy(
        update={"message": analysis_message, "clarification_selection": None, "client_message_id": None}
    )
    response = await _process_standard_chat(
        db,
        session,
        current_user,
        numeric_db_id,
        body_copy,
        can_generate_metrics,
        org_id,
        save_user_msg=False,
        clarified_dimensions=opt_dims,
        forced_intent="metric_query",
        is_clarified=True,
    )
    response.user_message_id = None
    response.clarification_resolution = resolution_payload
    return response


async def _try_execute_clarification_spec(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    prev_msg: ChatMessageModel,
    body: ChatRequest,
    spec_dict: dict,
    can_generate_metrics: bool,
    org_id: int | None = None,
) -> ChatResponse | None:
    """Execute a pre-validated clarification option spec, or None to delegate."""
    catalog = await _load_clarification_catalog(db, numeric_db_id, spec_dict)
    if catalog is None:
        return None
    _, live_db = await _query_target(db, numeric_db_id, current_user.id, org_id)
    outcome = await _compile_clarification_spec(
        db, session, current_user, numeric_db_id, org_id, live_db, catalog, spec_dict, body, can_generate_metrics
    )
    if isinstance(outcome, ChatResponse):
        return outcome
    return await _persist_clarification_spec_response(db, session, current_user, body, outcome, can_generate_metrics)


async def _load_clarification_catalog(db: AsyncSession, numeric_db_id: int, spec_dict: dict) -> dict | None:
    """Return the parser catalog if every spec metric id is approved, else None."""
    catalog = await build_parser_catalog(db, numeric_db_id)
    valid_ids = {m["id"] for m in catalog.get("metrics", [])}
    if not set(spec_dict["metric_ids"]).issubset(valid_ids):
        return None
    return catalog


async def _compile_clarification_spec(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    org_id: int | None,
    live_db: LiveTargetDbModel,
    catalog: dict,
    spec_dict: dict,
    body: ChatRequest,
    can_generate_metrics: bool,
) -> ChatResponse | ChatSemanticQueryResult:
    """Compile and run the clarification spec; return invalid ChatResponse on failure."""
    try:
        spec = SemanticQuerySpec(**spec_dict)
    except ValidationError as exc:
        logger.warning("Invalid clarification option spec: %s", exc)
        return await _invalid_clarification_option_response(
            db, session, current_user, body, can_generate_metrics, org_id
        )
    try:
        return await execute_natural_language_query(db, numeric_db_id, live_db, spec, catalog)
    except SemanticCompileError as exc:
        msg = getattr(exc, "message", str(exc))
        logger.warning("Semantic compile error for clarification option: %s (%s)", msg, exc.code)
        return await _invalid_clarification_option_response(
            db, session, current_user, body, can_generate_metrics, org_id
        )


async def _persist_clarification_spec_response(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    body: ChatRequest,
    query_result: ChatSemanticQueryResult,
    can_generate_metrics: bool,
) -> ChatResponse:
    """Persist the executed clarification spec as an assistant message and respond."""
    assistant = await save_chat_message(
        db,
        session.id,
        "assistant",
        query_result.explanation,
        intent="semantic_query",
        metadata_json=_assistant_metadata(semantic_query_result=query_result.model_dump(mode="json")),
        client_message_id=f"{body.client_message_id}:assistant" if body.client_message_id else None,
    )
    refreshed = await get_chat_session_with_messages(db, session.id, current_user.id)
    display_res = query_result if can_generate_metrics else query_result.model_copy(update={"sql": None})
    return ChatResponse(
        intent="semantic_query",
        chat_response=query_result.explanation,
        semantic_query_result=display_res,
        session_id=session.id,
        user_message_id=None,
        assistant_message_id=assistant.id,
        session=_session_summary(refreshed),
    )


_INVALID_OPTION_NOTICE = (
    "Lựa chọn không hợp lệ hoặc chỉ số được chọn không còn khả dụng trong danh mục "
    "được phê duyệt. Vui lòng chọn một tùy chọn khác hoặc đặt câu hỏi mới."
)


async def _invalid_clarification_option_response(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    body: ChatRequest,
    can_generate_metrics: bool,
    org_id: int | None = None,
) -> ChatResponse:
    """Persist and return the stable invalid-option Vietnamese notice for a bad clarification selection."""
    user_msg = await save_chat_message(db, session.id, "user", body.message, client_message_id=body.client_message_id)
    assistant = await save_chat_message(
        db,
        session.id,
        "assistant",
        _INVALID_OPTION_NOTICE,
        intent="semantic_query",
        metadata_json=_assistant_metadata(),
        client_message_id=f"{body.client_message_id}:assistant" if body.client_message_id else None,
    )
    refreshed = await get_chat_session_with_messages(db, session.id, current_user.id)
    return ChatResponse(
        intent="semantic_query",
        chat_response=_INVALID_OPTION_NOTICE,
        session_id=session.id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant.id,
        session=_session_summary(refreshed),
    )


async def _process_standard_chat(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    body: ChatRequest,
    can_generate_metrics: bool,
    org_id: int | None = None,
    chat_database: SemanticDatabaseModel | None = None,
    save_user_msg: bool = True,
    clarified_dimensions: list[str] | None = None,
    forced_intent: str | None = None,
    is_clarified: bool = False,
) -> ChatResponse:
    """Process a standard chat query through the graph and execution layer."""

    from src.agents.chat_graph import chat_agent
    from src.agents.nodes.orchestrator_node import orchestrator_node

    history = await get_recent_chat_history(db, session.id)
    user_message = None
    if save_user_msg:
        user_message = await save_chat_message(
            db, session.id, "user", body.message, client_message_id=body.client_message_id
        )
        if session.title == "Cuộc trò chuyện mới":
            await update_chat_session_title(db, session.id, current_user.id, auto_generate_session_title(body.message))
    approved_metrics = await _load_approved_metric_context(db, numeric_db_id)

    if forced_intent:
        preclassified_intent = forced_intent
        preclassified_chat_response = None
    else:
        classification = await orchestrator_node({"user_message": body.message, "chat_history": history})
        preclassified_intent = classification.get("intent", "semantic_query")
        preclassified_chat_response = classification.get("chat_response")

    parser_catalog: dict[str, Any] = {}
    if preclassified_intent in {"semantic_query", "metric_query"}:
        try:
            await _query_target(db, numeric_db_id, current_user.id, org_id)
        except Exception as err:
            logger.debug("Live DB query target check skipped: %s", err)
        parser_catalog = await build_parser_catalog(db, numeric_db_id)

    grounded_candidate_dims: list[dict[str, Any]] = []
    semantic_schema_text = ""
    if numeric_db_id and parser_catalog:
        grounded_candidate_dims, semantic_schema_text = await _discover_candidate_dimensions_for_query(
            db, numeric_db_id, parser_catalog, body.message
        )

    context = await _build_chat_context(
        db, numeric_db_id, body.message, preclassified_intent, get_settings().metric_context_token_budget, history
    )
    existing_metrics, dedupe_performed = await load_existing_for_dedupe(db, str(numeric_db_id))
    role = (
        await _chat_role(db, chat_database, current_user.id)
        if chat_database is not None
        else ("data_lead" if can_generate_metrics else "member")
    )
    final_state = await _chat_state_for_context(
        chat_agent,
        context,
        session.id,
        body.message,
        history,
        approved_metrics,
        can_generate_metrics,
        preclassified_intent,
        existing_metrics,
        dedupe_performed,
        parser_catalog,
        chat_response=preclassified_chat_response,
        role=role,
        grounded_candidate_dimensions=grounded_candidate_dims,
        semantic_schema_text=semantic_schema_text,
        clarified_dimensions=clarified_dimensions,
        is_clarified=is_clarified or bool(clarified_dimensions),
    )
    return await _build_and_save_chat_response(
        db,
        session,
        current_user,
        numeric_db_id,
        body,
        user_message,
        final_state,
        can_generate_metrics,
        dedupe_performed,
        context.diagnostic,
        parser_catalog,
        org_id,
    )


async def _build_and_save_chat_response(
    db: AsyncSession,
    session: ChatSessionModel,
    current_user: UserModel,
    numeric_db_id: int,
    body: ChatRequest,
    user_message: ChatMessageModel,
    final_state: dict[str, Any],
    can_generate_metrics: bool,
    dedupe_performed: bool,
    context_diagnostic: dict[str, Any],
    parser_catalog: dict[str, Any],
    org_id: int | None,
) -> ChatResponse:
    """Format, execute semantic queries if resolved, persist assistant message, and return response."""
    intent = final_state.get("intent", "chitchat")
    raw_metrics = final_state.get("suggested_metrics") or []
    response_text = final_state.get("chat_response", "")
    suggestion_action = final_state.get("suggestion_action")
    notices = final_state.get("duplicate_notices") or []
    performed = final_state.get("dedupe_performed", dedupe_performed)

    query_res, clar_payload = None, None
    if final_state.get("clarification") or (
        (intent == "semantic_query" or final_state.get("interpretation"))
        and not (intent == "metric_query" and raw_metrics)
    ):
        query_res, clar_payload, response_text = await _execute_or_clarify_semantic_query(
            db, numeric_db_id, current_user.id, org_id, final_state, parser_catalog
        )
        if clar_payload is not None or query_res is not None:
            intent = "semantic_query"
    elif intent == "metric_query":
        response_text = (
            response_text
            if (response_text and ("đề xuất" in response_text.lower() or "chỉ số" in response_text.lower()))
            else (
                f"Đã đề xuất {len(raw_metrics)} Metric Definition."
                if raw_metrics
                else (response_text or "Không sinh được metric phù hợp với schema.")
            )
        )

    assistant = await save_chat_message(
        db,
        session.id,
        "assistant",
        response_text,
        intent=intent,
        metadata_json=_assistant_metadata(
            raw_metrics,
            suggestion_action,
            duplicates=notices,
            dedupe_performed=performed,
            diagnostics=context_diagnostic,
            semantic_query_result=query_res.model_dump(mode="json") if query_res else None,
            clarification=clar_payload.model_dump(mode="json") if clar_payload else None,
        ),
        client_message_id=f"{body.client_message_id}:assistant" if body.client_message_id else None,
    )
    refreshed = await get_chat_session_with_messages(db, session.id, current_user.id)
    display_res = (
        query_res
        if (query_res and can_generate_metrics)
        else (query_res.model_copy(update={"sql": None}) if query_res else None)
    )
    return ChatResponse(
        intent=intent,
        chat_response=response_text
        if intent in {"chitchat", "data_question", "out_of_scope", "semantic_query"}
        else None,
        suggestions=raw_metrics if intent == "metric_query" else None,
        duplicates=notices if intent == "metric_query" else [],
        dedupe_performed=performed,
        suggestion_action=suggestion_action if intent == "metric_query" else None,
        diagnostics=_chat_diagnostics_for_role(context_diagnostic, can_generate_metrics),
        semantic_query_result=display_res,
        clarification=clar_payload,
        session_id=session.id,
        user_message_id=user_message.id if user_message is not None else None,
        assistant_message_id=assistant.id,
        session=_session_summary(refreshed),
    )


async def _execute_or_clarify_semantic_query(
    db: AsyncSession,
    numeric_db_id: int,
    user_id: int,
    org_id: int | None,
    final_state: dict[str, Any],
    parser_catalog: dict[str, Any],
) -> tuple[ChatSemanticQueryResult | None, ChatClarificationPayload | None, str]:
    """Prepare clarification payload or provide guidance without direct DB execution in chat."""
    clar = ChatClarificationPayload(**final_state["clarification"]) if final_state.get("clarification") else None
    if clar is not None:
        return None, clar, clar.prompt

    interp_raw = final_state.get("interpretation") or {}
    if interp_raw.get("clarification"):
        clar = ChatClarificationPayload(**interp_raw["clarification"])
        return None, clar, clar.prompt

    prompt = (
        final_state.get("chat_response")
        or "Hệ thống hỗ trợ tra cứu và phân tích số liệu trực tiếp tại tab **Metric Explorer**. "
        "Tại chat, tôi hỗ trợ giải thích cấu trúc dữ liệu và tạo mới các chỉ số (Business Metric)."
    )
    return None, None, prompt


async def _discover_candidate_dimensions_for_query(
    db: AsyncSession,
    numeric_db_id: int,
    parser_catalog: dict[str, Any],
    message: str,
) -> tuple[list[dict[str, Any]], str]:
    """Discover reachable multi-hop tables and dimensions without rule-based taxonomies."""
    metrics = parser_catalog.get("metrics") or []
    base_entities = [m.get("base_entity") for m in metrics if m.get("base_entity")]
    base_ids: list[int] = []
    if base_entities:
        stmt = select(SemanticTableModel.id).where(
            SemanticTableModel.db_id == numeric_db_id,
            SemanticTableModel.table_name.in_(base_entities),
        )
        base_ids = list((await db.execute(stmt)).scalars().all())

    schema_items = await get_reachable_semantic_schema(db, numeric_db_id, base_ids)
    schema_text = format_semantic_schema_for_prompt(schema_items)

    candidates = []
    for item in schema_items:
        for d in item["dimensions"]:
            label = f"{d['business_name']} (bảng {item['table_business_name']})"
            candidates.append(
                {
                    "column_id": d["column_id"],
                    "column_name": d["column_name"],
                    "business_name": d["business_name"],
                    "table_name": item["table_name"],
                    "table_business_name": item["table_business_name"],
                    "sample_values": d.get("sample_values", []),
                    "hop_count": item["hops"],
                    "label": label,
                }
            )
    return candidates, schema_text


async def _chat_state_for_context(
    chat_agent: Any,
    context: Any,
    session_id: str,
    message: str,
    history: list[dict[str, str]],
    approved_metrics: list[dict[str, Any]],
    can_generate_metrics: bool,
    intent: str,
    existing_metrics: list[dict[str, Any]] | None,
    dedupe_performed: bool,
    parser_catalog: dict[str, Any] | None = None,
    chat_response: str | None = None,
    role: str = "",
    grounded_candidate_dimensions: list[dict[str, Any]] | None = None,
    semantic_schema_text: str = "",
    clarified_dimensions: list[str] | None = None,
    is_clarified: bool = False,
) -> dict[str, Any]:
    """Run the graph only after consented context preparation succeeds."""
    if context.diagnostic.get("status") != "ready" and intent not in {"semantic_query", "metric_query"}:
        return {"intent": "data_question", "chat_response": context.diagnostic.get("message", "")}
    return await chat_agent.ainvoke(
        {
            "session_id": session_id,
            "user_message": message,
            "chat_history": history,
            "enriched_schema": context.schema,
            "approved_metrics": approved_metrics,
            "can_generate_metrics": can_generate_metrics,
            "role": role,
            "context_diagnostic": context.diagnostic,
            "intent": intent,
            "existing_metrics": existing_metrics or [],
            "dedupe_performed": dedupe_performed,
            "parser_catalog": parser_catalog or {},
            "chat_response": chat_response,
            "grounded_candidate_dimensions": grounded_candidate_dimensions or [],
            "semantic_schema_text": semantic_schema_text,
            "clarified_dimensions": clarified_dimensions or [],
            "is_clarified": is_clarified,
        }
    )


async def _build_chat_context(
    db: AsyncSession,
    db_id: int,
    message: str,
    intent: str,
    token_budget: int,
    history: list[dict[str, str]] | None = None,
) -> MetricContextResult:
    """Prepare context only after the request intent is known."""
    query = message
    if history and len(message.strip().split()) <= 6:
        prior_user_msgs = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")]
        if prior_user_msgs:
            query = f"{prior_user_msgs[-1]}\nYêu cầu tiếp theo: {message}"
    if intent in {"metric_query", "semantic_query"}:
        return await fast_metric_context(db, db_id)
    if intent == "data_question":
        return await build_data_context(db, db_id, query, token_budget)
    return MetricContextResult(schema={}, diagnostic={"status": "ready", "tables": [], "relationship_count": 0})


def _chat_diagnostics_for_role(diagnostic: dict[str, Any], can_generate_metrics: bool) -> dict[str, Any]:
    """Keep table-level diagnostics visible only to Data Leads."""
    if can_generate_metrics:
        return diagnostic
    return {key: value for key, value in diagnostic.items() if key in {"status", "message"}}


async def _resolve_chat_session(db: AsyncSession, session_id: str | None, user_id: int, db_id: int) -> ChatSessionModel:
    """Resolve an existing owned session or create a new one."""
    if session_id:
        session = await get_chat_session(db, session_id, user_id)
        if session is None or session.db_id != db_id:
            raise ChatAuthorizationError("Chat session not found")
        return session
    return await create_chat_session(db, user_id, db_id)


async def _replay_chat_response(
    db: AsyncSession,
    session: ChatSessionModel,
    user_id: int,
    client_message_id: str | None,
    can_generate_metrics: bool = False,
) -> ChatResponse | None:
    """Return a completed response for a retried client request."""
    if not client_message_id:
        return None
    user_message = await get_chat_message_by_client_id(db, session.id, client_message_id)
    assistant = await get_chat_message_by_client_id(db, session.id, f"{client_message_id}:assistant")
    if user_message is None or assistant is None:
        return None
    metadata = assistant.metadata_json if isinstance(assistant.metadata_json, dict) else {}
    suggestions = metadata.get("suggestions") or []
    suggestion_action = metadata.get("suggestion_action")
    duplicates = metadata.get("duplicates") or []
    intent = assistant.intent or "chitchat"

    query_res_dict = metadata.get("semantic_query_result")
    query_result = None
    if query_res_dict and isinstance(query_res_dict, dict):
        copied = dict(query_res_dict)
        if not can_generate_metrics:
            copied["sql"] = None
        query_result = ChatSemanticQueryResult(**copied)

    clar_dict = metadata.get("clarification")
    clar_payload = ChatClarificationPayload(**clar_dict) if clar_dict and isinstance(clar_dict, dict) else None

    refreshed = await get_chat_session_with_messages(db, session.id, user_id)
    if refreshed is None:
        return None
    return ChatResponse(
        intent=intent,
        chat_response=assistant.content
        if intent in {"chitchat", "data_question", "out_of_scope", "semantic_query"}
        else None,
        suggestions=suggestions if intent == "metric_query" else None,
        duplicates=duplicates if intent == "metric_query" else [],
        dedupe_performed=bool(metadata.get("dedupe_performed", True)),
        suggestion_action=suggestion_action if intent == "metric_query" else None,
        semantic_query_result=query_result,
        clarification=clar_payload,
        session_id=session.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant.id,
        session=_session_summary(refreshed),
    )
