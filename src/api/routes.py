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
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.schema_metadata import DiagnosticCode, SchemaDialect
from src.models.schemas import (
    ApproveRequest,
    ApproveResponse,
    CustomMetricGenerateRequest,
    CustomMetricGenerateResponse,
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
    UserProfileResponse,
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
from src.services.metrics import generate_metrics_from_prompt, normalize_prompt
from src.services.schema_ingestion import parse_sql_dump_preview
from src.services.sql_dump_parser_models import SqlDumpParseError
from src.services.sql_dump_scanner_models import SqlDumpScanError

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])

DEMO_RETAIL_SCHEMA: dict[str, Any] = {
    "order_header": {
        "business_name": "Đơn hàng",
        "description": "Bảng chứa thông tin tổng quan của đơn hàng",
        "columns": [
            {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "business_name": "Mã đơn hàng"},
            {"column_name": "customer_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã KH"},
            {"column_name": "store_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Mã cửa hàng"},
            {"column_name": "sales_channel_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Kênh bán"},
            {"column_name": "payment_method_id", "data_type": "INTEGER", "is_foreign_key": True, "business_name": "Phương thức thanh toán"},
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
# 3. Flow 1 — Generate & HITL
# ---------------------------------------------------------------------------


@router.post("/semantic/generate", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_semantic_layer(request: GenerateRequest) -> GenerateResponse:
    """Kick-off Flow 1: Introspect -> Enrich -> MetricSuggest -> HITL interrupt."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Flow 1 pipeline not yet implemented")


@router.post("/semantic/approve", response_model=ApproveResponse)
async def approve_semantic_layer(request: ApproveRequest) -> ApproveResponse:
    """HITL approval - Save Node: persist reviewed semantic layer to Metadata Store."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="HITL approval not yet implemented")


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
    """Helper to fetch schema context from database with eager loading or fallback to demo schema."""
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
                        }
                        for col in tbl.columns
                    ],
                }
            return schema_dict
    except (ValueError, TypeError):
        pass

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
async def create_metric(
    db_id: str,
    body: MetricCreate,
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Tạo hoặc lưu một Business Metric vào Semantic Layer."""
    numeric_db_id = int(db_id)
    new_metric = SemanticMetricModel(
        db_id=numeric_db_id,
        name=body.name,
        description=body.description,
        sql_template=body.sql_template,
        source=body.source,
    )
    db.add(new_metric)

    # If DB exists, update its status to 'draft'
    db_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == numeric_db_id)
    res = await db.execute(db_stmt)
    db_record = res.scalar_one_or_none()
    if db_record:
        db_record.status = "draft"

    await db.commit()
    await db.refresh(new_metric)

    return MetricResponse(
        metric_id=new_metric.id,
        name=new_metric.name,
        description=new_metric.description,
        sql_template=new_metric.sql_template,
        source=new_metric.source,
    )


@router.put("/semantic/{db_id}/metric/{metric_id}", response_model=MetricResponse)
async def update_metric(
    db_id: str,
    metric_id: int,
    body: MetricUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> MetricResponse:
    """Cập nhật công thức hoặc thông tin của một Business Metric."""
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    res = await db.execute(stmt)
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric with id {metric_id} not found")

    if body.name is not None:
        metric.name = body.name
    if body.description is not None:
        metric.description = body.description
    if body.sql_template is not None:
        metric.sql_template = body.sql_template

    try:
        numeric_db_id = int(db_id)
        db_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == numeric_db_id)
        db_res = await db.execute(db_stmt)
        db_record = db_res.scalar_one_or_none()
        if db_record:
            db_record.status = "draft"
    except ValueError:
        pass

    await db.commit()
    await db.refresh(metric)

    return MetricResponse(
        metric_id=metric.id,
        name=metric.name,
        description=metric.description,
        sql_template=metric.sql_template,
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
# 7. Health / Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def agent_status() -> dict:
    """Check agent readiness."""
    return {"status": "ready", "pipeline": "Flow 1 — Generate & Manage Semantic Layer"}
