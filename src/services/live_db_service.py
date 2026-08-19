"""Live Target Database Service.

Provides:
  - Zero-data schema introspection via SQLAlchemy Inspector.
  - Fernet encryption for connection URLs.
  - Persistence of live target database metadata in Metadata Store.
  - Auto-creation of SemanticDatabase and background enrichment for live DBs.
"""

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import LiveTargetDbModel, SemanticDatabaseModel
from src.models.schema_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
    default_schema_identifier,
)
from src.models.schemas import LiveDbResponse, LiveDbSummaryResponse
from src.services.database import encrypt_conn_url, get_db_session
from src.services.semantic_service import enrich_and_save_canonical_schema, ensure_semantic_database

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()

_SYNC_INSPECTION_DRIVERS = {
    "postgresql+asyncpg": "postgresql+psycopg2",
    "mysql+asyncmy": "mysql+pymysql",
    "mysql+aiomysql": "mysql+pymysql",
    "sqlite+aiosqlite": "sqlite",
}

_SAMPLE_LIMIT = 10

_CATEGORICAL_PATTERNS = (
    "status",
    "type",
    "flag",
    "is_",
    "has_",
    "category",
    "state",
    "level",
    "role",
    "gender",
    "priority",
)

_PII_PATTERNS = (
    "password",
    "secret",
    "token",
    "hash",
    "note",
    "comment",
    "email",
    "phone",
    "address",
    "ip_",
    "user_agent",
)


def _should_sample(col_name: str, raw_type: str) -> bool:
    """Heuristic: only sample categorical columns, block PII and long text."""
    name_lower = col_name.lower()
    if any(p in name_lower for p in _PII_PATTERNS):
        return False
    type_upper = raw_type.upper()
    if any(t in type_upper for t in ("BOOLEAN", "BOOL", "ENUM")):
        return True
    if any(t in type_upper for t in ("VARCHAR", "CHAR")):
        match = re.search(r"\((\d+)\)", type_upper)
        if match and int(match.group(1)) > 50:
            return False
        return any(pat in name_lower for pat in _CATEGORICAL_PATTERNS)
    if any(t in type_upper for t in ("SMALLINT", "TINYINT", "INT", "INTEGER")):
        return any(pat in name_lower for pat in _CATEGORICAL_PATTERNS)
    return False


def _sample_distinct_values(
    conn: Connection,
    table_name: str,
    column_name: str,
    schema_name: str | None,
    dialect: SchemaDialect,
) -> tuple[str, ...] | None:
    """Sample distinct values for a categorical column safely. Returns None on failure."""
    try:
        safe_col = column_name.replace('"', '""')
        safe_tbl = table_name.replace('"', '""')
        safe_schema = schema_name.replace('"', '""') if schema_name else None

        if dialect == SchemaDialect.POSTGRESQL:
            col_ref = f'"{safe_col}"'
            tbl_ref = f'"{safe_schema}"."{safe_tbl}"' if safe_schema else f'"{safe_tbl}"'
        elif dialect == SchemaDialect.MYSQL:
            safe_col_m = column_name.replace("`", "``")
            safe_tbl_m = table_name.replace("`", "``")
            col_ref = f"`{safe_col_m}`"
            tbl_ref = f"`{safe_tbl_m}`"
        else:
            col_ref = f'"{safe_col}"'
            tbl_ref = f'"{safe_tbl}"'

        sql = f"SELECT DISTINCT {col_ref} FROM {tbl_ref} WHERE {col_ref} IS NOT NULL LIMIT {_SAMPLE_LIMIT}"  # noqa: S608
        rows = conn.exec_driver_sql(sql).fetchall()
        if not rows:
            return None
        return tuple(str(row[0]) for row in rows)
    except Exception:
        return None


def _sync_introspection_url(conn_url: str) -> str:
    """Return an Inspector-safe URL while preserving credentials and options."""
    url = make_url(conn_url)
    driver_name = _SYNC_INSPECTION_DRIVERS.get(url.drivername)
    if driver_name is None:
        return conn_url
    return url.set(drivername=driver_name).render_as_string(hide_password=False)


def introspect_live_database(conn_url: str, dialect: str | SchemaDialect) -> RawSchemaMetadata:
    """Introspect technical schema metadata and sample categorical values from a live target database."""
    resolved_dialect = (
        dialect if isinstance(dialect, SchemaDialect) else resolve_and_validate_dialect(conn_url, dialect)
    )
    engine = create_engine(_sync_introspection_url(conn_url))
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            default_schema = default_schema_identifier(resolved_dialect)
            table_names = inspector.get_table_names()
            tables = []
            for table_name in table_names:
                table_meta = _introspect_table(inspector, table_name, default_schema, resolved_dialect, conn)
                if table_meta:
                    tables.append(table_meta)
            schema_meta = SchemaMetadata(schema_name=default_schema)
            return RawSchemaMetadata(
                dialect=resolved_dialect,
                schemas=(schema_meta,),
                tables=tuple(tables),
            )
    finally:
        engine.dispose()


def _introspect_table(
    inspector: Any,
    table_name: str,
    schema: Identifier,
    dialect: SchemaDialect,
    conn: Connection | None = None,
) -> TableMetadata | None:
    """Extract columns, PK, and FK metadata for a single table."""
    raw_columns = inspector.get_columns(table_name)
    if not raw_columns:
        return None
    pk_info = inspector.get_pk_constraint(table_name)
    pk_cols = set(pk_info.get("constrained_columns", [])) if pk_info else set()
    columns = _build_columns(raw_columns, pk_cols, dialect, conn, table_name, schema.raw_name)
    pk_meta = _build_pk(pk_info, schema, dialect) if pk_cols else None
    fk_list = _build_fks(inspector.get_foreign_keys(table_name), schema, dialect)
    return TableMetadata(
        schema_name=schema,
        table_name=Identifier.from_raw(table_name, dialect),
        columns=tuple(columns),
        primary_key=pk_meta,
        foreign_keys=tuple(fk_list),
    )


def _build_columns(
    raw_columns: list[dict[str, Any]],
    pk_cols: set[str],
    dialect: SchemaDialect,
    conn: Connection | None = None,
    table_name: str | None = None,
    schema_name: str | None = None,
) -> list[ColumnMetadata]:
    """Convert inspector raw columns to canonical ColumnMetadata list with safe categorical sampling."""
    columns = []
    for idx, col in enumerate(raw_columns, start=1):
        col_name = col["name"]
        raw_type = str(col["type"])
        col_ident = Identifier.from_raw(col_name, dialect)
        is_pk = col_name in pk_cols
        sample_vals = None
        if conn is not None and table_name and _should_sample(col_name, raw_type):
            sample_vals = _sample_distinct_values(conn, table_name, col_name, schema_name, dialect)
        columns.append(
            ColumnMetadata(
                column_name=col_ident,
                ordinal_position=idx,
                raw_data_type=raw_type,
                data_type=raw_type.upper(),
                nullable=bool(col.get("nullable", True)),
                default_expression=str(col["default"]) if col.get("default") is not None else None,
                primary_key=is_pk,
                sample_values=sample_vals,
            )
        )
    return columns


def _build_pk(pk_info: dict[str, Any], schema: Identifier, dialect: SchemaDialect) -> PrimaryKeyMetadata | None:
    """Build PrimaryKeyMetadata from inspector pk constraint dict."""
    constrained = pk_info.get("constrained_columns", [])
    if not constrained:
        return None
    c_name = pk_info.get("name")
    name_ident = Identifier.from_raw(c_name, dialect) if c_name else None
    cols = tuple(Identifier.from_raw(c, dialect) for c in constrained)
    return PrimaryKeyMetadata(constraint_name=name_ident, constrained_columns=cols)


def _build_fks(
    raw_fks: list[dict[str, Any]], default_schema: Identifier, dialect: SchemaDialect
) -> list[ForeignKeyMetadata]:
    """Build ForeignKeyMetadata list from inspector foreign keys dicts."""
    fks = []
    for fk in raw_fks:
        c_cols = fk.get("constrained_columns", [])
        r_cols = fk.get("referred_columns", [])
        ref_table = fk.get("referred_table")
        if not c_cols or not r_cols or not ref_table or len(c_cols) != len(r_cols):
            continue
        c_name = fk.get("name")
        c_ident = Identifier.from_raw(c_name, dialect) if c_name else None
        ref_schema = fk.get("referred_schema")
        s_ident = Identifier.from_raw(ref_schema, dialect) if ref_schema else default_schema
        fks.append(
            ForeignKeyMetadata(
                constraint_name=c_ident,
                constrained_columns=tuple(Identifier.from_raw(c, dialect) for c in c_cols),
                referred_schema=s_ident,
                referred_table=Identifier.from_raw(ref_table, dialect),
                referred_columns=tuple(Identifier.from_raw(r, dialect) for r in r_cols),
            )
        )
    return fks


def resolve_and_validate_dialect(conn_url: str, dialect_choice: str | SchemaDialect | None) -> SchemaDialect:
    """Auto-detect dialect from connection URL if auto, or strictly validate match if explicitly specified."""
    url_lower = conn_url.strip().lower()
    detected: SchemaDialect | None = None
    if url_lower.startswith(("postgresql://", "postgresql+")):
        detected = SchemaDialect.POSTGRESQL
    elif url_lower.startswith(("mysql://", "mysql+", "mariadb+")):
        detected = SchemaDialect.MYSQL
    elif url_lower.startswith(("sqlite://", "sqlite+")):
        detected = SchemaDialect.SQLITE

    raw_choice = (
        dialect_choice.value
        if isinstance(dialect_choice, SchemaDialect)
        else (dialect_choice or "auto").strip().lower()
    )

    if raw_choice in ("auto", "none", ""):
        if detected is None:
            raise ValueError(
                "Cannot auto-detect database dialect from connection URL. Please specify the dialect manually."
            )
        return detected

    try:
        chosen_dialect = SchemaDialect(raw_choice)
    except ValueError as exc:
        raise ValueError(f"Unsupported database dialect '{raw_choice}'") from exc

    if detected is not None and detected != chosen_dialect:
        raise ValueError(
            f"Connection URL scheme does not match selected dialect '{chosen_dialect.value}' (detected '{detected.value}')"
        )
    return chosen_dialect


async def create_live_target_db(
    db: AsyncSession,
    user_id: int,
    display_name: str,
    dialect: str | SchemaDialect | None,
    conn_url: str,
    org_id: int | None = None,
) -> LiveDbResponse:
    """Introspect live database, encrypt connection URL, and save record."""
    logger.info("Connecting and introspecting live target DB '%s'...", display_name)
    resolved_dialect = resolve_and_validate_dialect(conn_url, dialect)
    raw_schema = introspect_live_database(conn_url, resolved_dialect)
    logger.info(
        "Introspection completed for '%s': dialect=%s, tables_found=%d",
        display_name,
        resolved_dialect.value,
        len(raw_schema.tables),
    )
    conn_url_enc = encrypt_conn_url(conn_url)
    model = LiveTargetDbModel(
        created_by=user_id,
        display_name=display_name,
        dialect=resolved_dialect.value,
        conn_url_enc=conn_url_enc,
        schema_metadata=raw_schema.model_dump(mode="json"),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    logger.info("Saved LiveTargetDbModel record ID=%d for '%s'", model.id, display_name)

    try:
        semantic_db_id = await ensure_semantic_database(
            db=db,
            source_type="live_target_db",
            source_id=model.id,
            user_id=user_id,
            display_name=display_name,
            dialect=resolved_dialect.value,
            org_id=org_id,
        )
        model.semantic_db_id = semantic_db_id
        await db.commit()
        await db.refresh(model)

        logger.info(
            "Created SemanticDatabaseModel ID=%d for live DB %d. Dispatching background AI enrichment task...",
            semantic_db_id,
            model.id,
        )
        task = asyncio.create_task(
            _run_enrichment_background(
                user_id=user_id,
                connection_id=semantic_db_id,
                raw_schema=raw_schema,
                dialect=resolved_dialect.value,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception:
        logger.warning("Failed to create semantic database for live DB %d", model.id, exc_info=True)

    return _model_to_response(model, raw_schema)


async def list_live_target_dbs(db: AsyncSession, user_id: int, org_id: int | None = None) -> list[LiveDbSummaryResponse]:
    """List live target databases owned by a user."""
    stmt = select(LiveTargetDbModel).order_by(LiveTargetDbModel.updated_at.desc())
    if org_id is None:
        stmt = stmt.where(LiveTargetDbModel.created_by == user_id)
    else:
        stmt = stmt.outerjoin(
            SemanticDatabaseModel, LiveTargetDbModel.semantic_db_id == SemanticDatabaseModel.id
        ).where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (LiveTargetDbModel.created_by == user_id))
        )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_model_to_summary(record) for record in records]


def _safe_raw_schema(schema_metadata: Any, model_dialect: str) -> RawSchemaMetadata:
    """Safely parse schema metadata or construct a valid fallback RawSchemaMetadata."""
    dialect_str = (model_dialect or "sqlite").lower()
    if dialect_str in ("postgres", "postgresql"):
        dialect = SchemaDialect.POSTGRESQL
    elif dialect_str in ("mysql", "mariadb"):
        dialect = SchemaDialect.MYSQL
    else:
        dialect = SchemaDialect.SQLITE

    default_schema = default_schema_identifier(dialect)
    fallback = RawSchemaMetadata(
        dialect=dialect,
        schemas=(SchemaMetadata(schema_name=default_schema),),
        tables=(),
    )

    if not schema_metadata:
        return fallback

    if isinstance(schema_metadata, str):
        try:
            schema_metadata = json.loads(schema_metadata)
        except Exception:
            return fallback

    if isinstance(schema_metadata, dict):
        try:
            return RawSchemaMetadata.model_validate(schema_metadata)
        except Exception:
            logger.debug("Failed to validate schema_metadata against RawSchemaMetadata, returning empty fallback")
            return fallback

    return fallback


def _model_to_summary(model: LiveTargetDbModel) -> LiveDbSummaryResponse:
    """Convert model to LiveDbSummaryResponse."""
    raw_schema = _safe_raw_schema(model.schema_metadata, model.dialect)
    return LiveDbSummaryResponse(
        id=model.id,
        semantic_db_id=model.semantic_db_id,
        display_name=model.display_name,
        dialect=raw_schema.dialect,
        table_count=len(raw_schema.tables),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_to_response(model: LiveTargetDbModel, raw_schema: RawSchemaMetadata) -> LiveDbResponse:
    """Convert model and raw schema to LiveDbResponse."""
    return LiveDbResponse(
        id=model.id,
        semantic_db_id=model.semantic_db_id,
        display_name=model.display_name,
        dialect=raw_schema.dialect,
        table_count=len(raw_schema.tables),
        created_at=model.created_at,
        updated_at=model.updated_at,
        raw_schema=raw_schema,
    )


async def get_live_target_db(
    db: AsyncSession, user_id: int, db_id: int, org_id: int | None = None
) -> LiveDbResponse | None:
    """Retrieve one user-owned live target database by ID."""
    stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.id == db_id)
    if org_id is None:
        stmt = stmt.where(LiveTargetDbModel.created_by == user_id)
    else:
        stmt = stmt.outerjoin(
            SemanticDatabaseModel, LiveTargetDbModel.semantic_db_id == SemanticDatabaseModel.id
        ).where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (LiveTargetDbModel.created_by == user_id))
        )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return None
    raw_schema = _safe_raw_schema(record.schema_metadata, record.dialect)
    return _model_to_response(record, raw_schema)


async def delete_live_target_db(
    db: AsyncSession, user_id: int, db_id: int, org_id: int | None = None
) -> bool:
    """Delete a user-owned live target database record and all related semantic layer metadata."""
    stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.id == db_id)
    if org_id is None:
        stmt = stmt.where(LiveTargetDbModel.created_by == user_id)
    else:
        stmt = stmt.outerjoin(
            SemanticDatabaseModel, LiveTargetDbModel.semantic_db_id == SemanticDatabaseModel.id
        ).where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (LiveTargetDbModel.created_by == user_id))
        )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False

    sem_db_id = record.semantic_db_id
    await db.delete(record)

    if sem_db_id:
        sem_db = await db.get(SemanticDatabaseModel, sem_db_id)
        if sem_db:
            await db.delete(sem_db)
    else:
        conn_key = f"semantic:live:{db_id}"
        sem_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.conn_url_enc == conn_key)
        sem_db = (await db.execute(sem_stmt)).scalar_one_or_none()
        if sem_db:
            await db.delete(sem_db)

    await db.commit()
    return True


async def _run_enrichment_background(
    user_id: int,
    connection_id: int,
    raw_schema: RawSchemaMetadata,
    dialect: str,
) -> None:
    """Run schema enrichment in background with its own DB session."""
    logger.info(
        "Starting background AI semantic enrichment for connection_id=%d (%d tables)...",
        connection_id,
        len(raw_schema.tables),
    )
    try:
        async for session in get_db_session():
            await enrich_and_save_canonical_schema(
                db=session,
                user_id=user_id,
                connection_id=connection_id,
                raw_schema=raw_schema,
                dialect=dialect,
            )
            await session.commit()
            logger.info("Successfully completed AI semantic enrichment for connection_id=%d", connection_id)
    except Exception as exc:
        logger.warning("Background enrichment failed for connection_id=%d: %s", connection_id, exc, exc_info=True)
