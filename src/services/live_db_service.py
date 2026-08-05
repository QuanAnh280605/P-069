"""Live Target Database Service.

Provides:
  - Zero-data schema introspection via SQLAlchemy Inspector.
  - Fernet encryption for connection URLs.
  - Persistence of live target database metadata in Metadata Store.
"""

from typing import Any

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import LiveTargetDbModel
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
from src.services.database import encrypt_conn_url


def introspect_live_database(conn_url: str, dialect: SchemaDialect) -> RawSchemaMetadata:
    """Introspect technical schema metadata from a live target database without executing data queries."""
    engine = create_engine(conn_url)
    try:
        inspector = inspect(engine)
        default_schema = default_schema_identifier(dialect)
        table_names = inspector.get_table_names()
        tables = []
        for table_name in table_names:
            table_meta = _introspect_table(inspector, table_name, default_schema, dialect)
            if table_meta:
                tables.append(table_meta)
        schema_meta = SchemaMetadata(schema_name=default_schema)
        return RawSchemaMetadata(
            dialect=dialect,
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
) -> TableMetadata | None:
    """Extract columns, PK, and FK metadata for a single table."""
    raw_columns = inspector.get_columns(table_name)
    if not raw_columns:
        return None
    pk_info = inspector.get_pk_constraint(table_name)
    pk_cols = set(pk_info.get("constrained_columns", [])) if pk_info else set()
    columns = _build_columns(raw_columns, pk_cols, dialect)
    pk_meta = _build_pk(pk_info, schema, dialect) if pk_cols else None
    fk_list = _build_fks(inspector.get_foreign_keys(table_name), schema, dialect)
    return TableMetadata(
        schema_name=schema,
        table_name=Identifier.from_raw(table_name, dialect),
        columns=tuple(columns),
        primary_key=pk_meta,
        foreign_keys=tuple(fk_list),
    )


def _build_columns(raw_columns: list[dict[str, Any]], pk_cols: set[str], dialect: SchemaDialect) -> list[ColumnMetadata]:
    """Convert inspector raw columns to canonical ColumnMetadata list."""
    columns = []
    for idx, col in enumerate(raw_columns, start=1):
        col_name = col["name"]
        raw_type = str(col["type"])
        col_ident = Identifier.from_raw(col_name, dialect)
        is_pk = col_name in pk_cols
        columns.append(
            ColumnMetadata(
                column_name=col_ident,
                ordinal_position=idx,
                raw_data_type=raw_type,
                data_type=raw_type.upper(),
                nullable=bool(col.get("nullable", True)),
                default_expression=str(col["default"]) if col.get("default") is not None else None,
                primary_key=is_pk,
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


def _build_fks(raw_fks: list[dict[str, Any]], default_schema: Identifier, dialect: SchemaDialect) -> list[ForeignKeyMetadata]:
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


async def create_live_target_db(
    db: AsyncSession,
    user_id: int,
    display_name: str,
    dialect: SchemaDialect,
    conn_url: str,
) -> LiveDbResponse:
    """Introspect live database, encrypt connection URL, and save record."""
    raw_schema = introspect_live_database(conn_url, dialect)
    conn_url_enc = encrypt_conn_url(conn_url)
    model = LiveTargetDbModel(
        created_by=user_id,
        display_name=display_name,
        dialect=dialect.value,
        conn_url_enc=conn_url_enc,
        schema_metadata=raw_schema.model_dump(mode="json"),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_to_response(model, raw_schema)


async def list_live_target_dbs(db: AsyncSession, user_id: int) -> list[LiveDbSummaryResponse]:
    """List live target databases owned by a user."""
    stmt = (
        select(LiveTargetDbModel)
        .where(LiveTargetDbModel.created_by == user_id)
        .order_by(LiveTargetDbModel.updated_at.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_model_to_summary(record) for record in records]


async def get_live_target_db(db: AsyncSession, user_id: int, db_id: int) -> LiveDbResponse | None:
    """Retrieve one user-owned live target database by ID."""
    stmt = select(LiveTargetDbModel).where(
        LiveTargetDbModel.id == db_id,
        LiveTargetDbModel.created_by == user_id,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return None
    raw_schema = RawSchemaMetadata.model_validate(record.schema_metadata)
    return _model_to_response(record, raw_schema)


async def delete_live_target_db(db: AsyncSession, user_id: int, db_id: int) -> bool:
    """Delete a user-owned live target database record."""
    stmt = select(LiveTargetDbModel).where(
        LiveTargetDbModel.id == db_id,
        LiveTargetDbModel.created_by == user_id,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return False
    await db.delete(record)
    await db.commit()
    return True


def _model_to_summary(model: LiveTargetDbModel) -> LiveDbSummaryResponse:
    """Convert model to LiveDbSummaryResponse."""
    raw_schema = RawSchemaMetadata.model_validate(model.schema_metadata)
    return LiveDbSummaryResponse(
        id=model.id,
        display_name=model.display_name,
        dialect=SchemaDialect(model.dialect),
        table_count=len(raw_schema.tables),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_to_response(model: LiveTargetDbModel, raw_schema: RawSchemaMetadata) -> LiveDbResponse:
    """Convert model and raw schema to LiveDbResponse."""
    return LiveDbResponse(
        id=model.id,
        display_name=model.display_name,
        dialect=SchemaDialect(model.dialect),
        table_count=len(raw_schema.tables),
        created_at=model.created_at,
        updated_at=model.updated_at,
        raw_schema=raw_schema,
    )
