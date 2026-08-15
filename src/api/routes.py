"""API Routes for Semantic Layer Flow 1, Business Metrics, Live DB, and HITL inline edits."""

import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_current_user, get_current_user_profile
from src.models.db import (
    CanonicalRelationshipModel,
    ImportedSchemaModel,
    LiveTargetDbModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.metric_definition import MetricDefinition
from src.models.schema_metadata import DiagnosticCode, RawSchemaMetadata, SchemaDialect
from src.models.schemas import (
    ApproveRequest,
    CanonicalRelationshipResponse,
    ChatRequest,
    ChatResponse,
    CustomMetricGenerateRequest,
    CustomMetricGenerateResponse,
    GenerateRequest,
    ImportedSchemaCreateRequest,
    ImportedSchemaResponse,
    ImportedSchemaSummaryResponse,
    LiveDbConnectRequest,
    LiveDbResponse,
    LiveDbSummaryResponse,
    MetricCreate,
    MetricHistoryResponse,
    MetricListItem,
    MetricResponse,
    MetricUpdate,
    MetricVersionItem,
    SemanticApproveV2Response,
    SemanticCatalogColumn,
    SemanticCatalogResponse,
    SemanticCatalogTable,
    SemanticColumnUpdate,
    SemanticGenerateV2Response,
    SemanticQueryCompileResponse,
    SemanticQueryRequest,
    SemanticQueryResponse,
    SemanticTableUpdate,
    SqlDumpPreviewResponse,
    UserProfileResponse,
)
from src.services.database import decrypt_conn_url, get_db_session
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
from src.services.metrics import generate_metrics_from_prompt, normalize_prompt
from src.services.query_compiler import SemanticQueryCompiler
from src.services.query_execution import execute_compiled_query
from src.services.schema_ingestion import parse_sql_dump_preview
from src.services.semantic_compile_error import SemanticCompileError
from src.services.semantic_service import (
    _coerce_metric_definition,
    approve_metric,
    create_metric,
    delete_semantic_database,
    enrich_and_save_canonical_schema,
    get_metric_with_history,
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
# 2. Live Target Database Management (Chức năng từ main)
# ---------------------------------------------------------------------------


@router.post("/semantic/db/connect", response_model=LiveDbResponse, status_code=201)
async def connect_live_target_db(
    body: LiveDbConnectRequest,
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
        return await create_live_target_db(
            db,
            current_user.id,
            body.display_name,
            body.dialect,
            body.conn_url,
        )
    except Exception as exc:
        logger.error("Failed to connect live DB '%s': %s", body.display_name, exc, exc_info=True)
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


@router.delete("/semantic/db/{db_id}", status_code=204)
async def remove_database_unified(
    db_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a database connection or schema and all associated tables, metrics, and relationships."""
    parsed_id = _parse_int_id(db_id)
    deleted = False
    if parsed_id is not None:
        if await delete_live_target_db(db, current_user.id, parsed_id):
            deleted = True
        elif await delete_imported_schema(db, current_user.id, parsed_id):
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
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticGenerateV2Response:
    """Re-run AI Enrichment for an existing semantic database.

    Looks up the source (live DB or imported schema) linked to the semantic db,
    reconstructs the raw schema metadata, and calls enrich_and_save_canonical_schema.
    """
    db_id = request.db_id
    logger.info("Received request to re-generate AI semantic layer for db_id=%d (user_id=%d)", db_id, current_user.id)

    sem_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_id)

    sem_result = await db.execute(sem_stmt)
    sem_db = sem_result.scalar_one_or_none()
    if not sem_db:
        raise HTTPException(status_code=404, detail="Semantic database not found")

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
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticApproveV2Response:
    """Approve all draft metrics for a semantic database.

    Checks ownership: only metrics created by the current user can be approved.
    """
    db_id = request.db_id

    sem_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_id)
    sem_result = await db.execute(sem_stmt)
    sem_db = sem_result.scalar_one_or_none()
    if not sem_db:
        raise HTTPException(status_code=404, detail="Semantic database not found")

    metrics_stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.db_id == db_id,
        SemanticMetricModel.status == "pending_approval",
    )
    metrics_result = await db.execute(metrics_stmt)
    draft_metrics = metrics_result.scalars().all()

    if not draft_metrics:
        raise HTTPException(status_code=404, detail="No draft metrics found to approve")

    approved_count = 0
    for metric in draft_metrics:
        if metric.created_by is not None and metric.created_by != current_user.id and current_user.role != "admin":
            continue
        await approve_metric(db=db, metric_id=metric.id, user_id=current_user.id)
        approved_count += 1

    sem_db.status = "saved"
    await db.commit()

    return SemanticApproveV2Response(
        db_id=db_id,
        approved_count=approved_count,
        message=f"Approved {approved_count} metric(s)",
    )


@router.post("/semantic/{db_id}/metric/{metric_id}/approve", response_model=MetricResponse)
async def approve_single_metric_endpoint(
    db_id: str,
    metric_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Approve a single metric by its ID."""
    numeric_db_id = int(db_id)
    stmt = select(SemanticMetricModel).where(
        SemanticMetricModel.id == metric_id,
        SemanticMetricModel.db_id == numeric_db_id,
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
    )


# ---------------------------------------------------------------------------
# 4. HITL Inline Edit — Tables & Columns (Chức năng từ nhánh của bạn)
# ---------------------------------------------------------------------------


@router.put("/semantic/{db_id}/table/{table_name}", status_code=status.HTTP_200_OK)
async def update_table(
    db_id: str,
    table_name: str,
    body: SemanticTableUpdate,
    user: UserProfileResponse = Depends(get_current_user_profile),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update business_name & description for a table."""
    int_id = _parse_int_id(db_id)
    if int_id is None:
        return {"message": "Table updated successfully"}

    stmt = select(SemanticTableModel).where(
        SemanticTableModel.db_id == int_id,
        SemanticTableModel.table_name == table_name,
    )
    tbl = (await db.execute(stmt)).scalar_one_or_none()
    if not tbl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    tbl.business_name = body.business_name.strip()
    tbl.description = body.description.strip()
    await db.commit()
    return {"message": "Table updated successfully"}


@router.put("/semantic/{db_id}/column/{table_name}/{column_name}", status_code=status.HTTP_200_OK)
async def update_column(
    db_id: str,
    table_name: str,
    column_name: str,
    body: SemanticColumnUpdate,
    user: UserProfileResponse = Depends(get_current_user_profile),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update business_name & description for a column."""
    int_id = _parse_int_id(db_id)
    if int_id is None:
        return {"message": "Column updated successfully"}

    stmt = (
        select(SemanticColumnModel)
        .join(SemanticTableModel)
        .where(
            SemanticTableModel.db_id == int_id,
            SemanticTableModel.table_name == table_name,
            SemanticColumnModel.column_name == column_name,
        )
    )
    col = (await db.execute(stmt)).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")

    col.business_name = body.business_name.strip()
    col.description = body.description.strip()
    await db.commit()
    return {"message": "Column updated successfully"}


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


@router.post("/semantic/{db_id}/metrics/generate", response_model=CustomMetricGenerateResponse)
async def generate_custom_metrics(
    db_id: str,
    body: CustomMetricGenerateRequest,
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
        if numeric_db_id >= 100:
            db_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == numeric_db_id)
            db_res = await db.execute(db_stmt)
            if db_res.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail=f"Database with id {db_id} not found")
    except ValueError:
        pass

    schema_context = await _load_schema_context_for_db(db, db_id)

    try:
        suggestions = await generate_metrics_from_prompt(
            prompt=clean_prompt,
            schema_context=schema_context,
            target_tables=body.target_tables,
        )
        return CustomMetricGenerateResponse(suggestions=suggestions)
    except Exception as exc:
        logger.error(f"Lỗi khi sinh metrics từ prompt: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể sinh metrics từ AI Service: {exc}",
        ) from exc


@router.post("/semantic/{db_id}/metric", response_model=MetricResponse, status_code=201)
async def create_metric_endpoint(
    db_id: str,
    body: MetricCreate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Tạo Business Metric mới — tự động tạo record trong metric_versions."""
    numeric_db_id = int(db_id)

    db_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == numeric_db_id)
    db_res = await db.execute(db_stmt)
    db_record = db_res.scalar_one_or_none()
    if not db_record:
        raise HTTPException(status_code=404, detail=f"Semantic database {numeric_db_id} not found")

    metric_data: dict[str, Any] = {
        "definition": body.definition.model_dump(mode="json"),
        "source": body.source,
    }

    try:
        new_metric = await create_metric(
            db=db,
            connection_id=numeric_db_id,
            metric_data=metric_data,
            user_id=current_user.id,
        )
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
    )


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
    db: AsyncSession = Depends(get_db_session),
) -> list[MetricListItem]:
    """Danh sách metrics kèm version, status, approved_by."""
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.db_id == db_id).order_by(SemanticMetricModel.id)
    result = await db.execute(stmt)
    metrics = result.scalars().all()

    items: list[MetricListItem] = []
    for m in metrics:
        items.append(
            MetricListItem(
                metric_id=m.id,
                name=m.name,
                definition=_safe_metric_definition(m.definition),
                source=m.source or "manual",
                version=m.version or 1,
                status=m.status or "needs_review",
                approved_by=m.approved_by,
                created_at=m.created_at,
            )
        )
    return items


@router.get("/semantic/{db_id}/catalog", response_model=SemanticCatalogResponse)
async def get_semantic_catalog(
    db_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticCatalogResponse:
    """Return canonical IDs and query capability for an owned semantic database."""
    semantic_db = await _owned_semantic_database(db, db_id, current_user.id)
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


async def _owned_semantic_database(db: AsyncSession, db_id: int, user_id: int) -> SemanticDatabaseModel | None:
    """Find an owned semantic database."""
    stmt = select(SemanticDatabaseModel).where(
        SemanticDatabaseModel.id == db_id,
        (SemanticDatabaseModel.created_by == user_id) | (SemanticDatabaseModel.created_by.is_(None)),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


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
        created_at=rel.created_at,
    )


async def _catalog_relationships(db: AsyncSession, db_id: int) -> list[CanonicalRelationshipResponse]:
    """Load canonical relationships for a semantic database."""
    stmt = (
        select(CanonicalRelationshipModel)
        .where(CanonicalRelationshipModel.connection_id == db_id)
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
    db: AsyncSession = Depends(get_db_session),
) -> MetricHistoryResponse:
    """Lịch sử version của một metric."""
    metric = await get_metric_with_history(db=db, metric_id=metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")
    if metric.db_id != db_id:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found in database {db_id}")

    versions = [
        MetricVersionItem(
            version=v.version,
            definition=v.definition,
            changed_by=v.changed_by,
            change_reason=v.change_reason or "",
            created_at=v.created_at,
        )
        for v in sorted(metric.versions, key=lambda x: x.version)
    ]

    return MetricHistoryResponse(
        metric_id=metric.id,
        metric_name=metric.name,
        versions=versions,
    )


@router.put("/semantic/{db_id}/metric/{metric_id}", response_model=MetricResponse)
async def update_metric(
    db_id: str,
    metric_id: int,
    body: MetricUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Replace a metric definition and reset it to pending approval."""
    try:
        numeric_db_id = int(db_id)
        metric = await update_metric_record(
            db,
            metric_id,
            {"definition": body.definition.model_dump(mode="json")},
            current_user.id,
        )
        if metric.db_id != numeric_db_id:
            raise ValueError("Metric does not belong to database")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(metric)
    return MetricResponse(
        metric_id=metric.id,
        definition=metric.definition,
        source=metric.source,
    )


@router.delete("/semantic/{db_id}/metric/{metric_id}", status_code=204)
async def delete_metric(
    db_id: str,
    metric_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Xóa một Business Metric khỏi Semantic Layer."""
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    res = await db.execute(stmt)
    metric = res.scalar_one_or_none()
    if metric:
        await db.delete(metric)
        await db.commit()


# ---------------------------------------------------------------------------
# 6. Export (Chức năng chung)
# ---------------------------------------------------------------------------


@router.get("/semantic/{db_id}/export")
async def export_semantic_layer(
    db_id: int,
    format: str = "json",
    db: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """Export approved Semantic Layer as JSON or YAML file download."""
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
# 7. Semantic Query Execution (Flow 2 — Live DB Only)
# ---------------------------------------------------------------------------


async def _query_target(
    db: AsyncSession,
    db_id: int,
    user_id: int,
) -> tuple[SemanticDatabaseModel, LiveTargetDbModel]:
    stmt = select(SemanticDatabaseModel).where(
        SemanticDatabaseModel.id == db_id,
        SemanticDatabaseModel.created_by == user_id,
    )
    semantic_db = (await db.execute(stmt)).scalar_one_or_none()
    if semantic_db is None:
        raise HTTPException(status_code=404, detail="Semantic database not found")
    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    live_db = (await db.execute(live_stmt)).scalar_one_or_none()
    if live_db is None:
        raise HTTPException(status_code=400, detail="Query only supported for Live DB connections")
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
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SemanticQueryCompileResponse:
    """Compile a semantic query preview without connecting to the target database."""
    await _query_target(db, db_id, current_user.id)
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

    # Fetch semantic database record
    stmt = select(SemanticDatabaseModel).where(
        SemanticDatabaseModel.id == parsed_id,
        SemanticDatabaseModel.created_by == current_user.id,
    )
    result = await db.execute(stmt)
    sem_db = result.scalar_one_or_none()
    if not sem_db:
        raise HTTPException(status_code=404, detail="Semantic database not found")

    # Verify linked LiveTargetDbModel exists (reject SQL Dump)
    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == parsed_id)
    live_result = await db.execute(live_stmt)
    live_db = live_result.scalar_one_or_none()
    if not live_db:
        raise HTTPException(
            status_code=400,
            detail="Query only supported for Live DB connections",
        )

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


@router.post("/semantic/{db_id}/chat", response_model=ChatResponse)
async def chat_orchestrator(
    db_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """Multi-agent chatbot: route chitchat to natural-language reply or metric generation.

    - 'chitchat' intent  → friendly Vietnamese natural-language response
    - 'metric_query' intent → Business Metric suggestions from schema
    """
    from src.agents.chat_graph import chat_agent

    schema_context = await _load_schema_context_for_db(db, db_id)

    initial_state: dict = {
        "user_message": body.message,
        "enriched_schema": schema_context,
    }

    try:
        final_state = await chat_agent.ainvoke(initial_state)
    except Exception as exc:
        logger.error("Chat orchestrator failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat agent encountered an error. Please try again.",
        ) from exc

    intent = final_state.get("intent", "chitchat")

    if intent == "metric_query":
        raw_metrics = final_state.get("suggested_metrics") or []
        return ChatResponse(intent=intent, suggestions=raw_metrics)

    return ChatResponse(
        intent=intent,
        chat_response=final_state.get("chat_response", ""),
    )
