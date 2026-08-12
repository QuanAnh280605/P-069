"""Save Node — Flow 1 Step 5 (after HITL approval).

Persist approved Semantic Layer into Metadata Store via semantic_service.
Converts pipeline RawSchema (TypedDict) to RawSchemaMetadata (Pydantic) before
calling enrich_and_save_canonical_schema().
"""

from __future__ import annotations

import logging

from src.agents.state import AgentState
from src.models.raw_schema import RawSchema
from src.models.schema_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)
from src.services.database import get_db_session
from src.services.semantic_service import enrich_and_save_canonical_schema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TypedDict -> Pydantic conversion
# ---------------------------------------------------------------------------


def raw_schema_to_canonical(raw: RawSchema, dialect: str) -> RawSchemaMetadata:
    """Convert pipeline TypedDict RawSchema to Pydantic RawSchemaMetadata."""
    schema_dialect = SchemaDialect(dialect)
    tables: list[TableMetadata] = []
    schemas_seen: dict[str, SchemaMetadata] = {}

    for tbl in raw.get("tables", []):
        schema_name_raw: str = tbl.get("schema_name") or _default_schema(schema_dialect)
        if schema_name_raw not in schemas_seen:
            schemas_seen[schema_name_raw] = SchemaMetadata(
                schema_name=Identifier.from_raw(schema_name_raw, schema_dialect),
            )

        columns = tuple(
            _convert_column(col, pos, schema_dialect) for pos, col in enumerate(tbl.get("columns", []), start=1)
        )
        pk = _convert_primary_key(tbl.get("primary_keys", []), schema_dialect)
        fks = tuple(_convert_fk(fk, schema_dialect) for fk in tbl.get("foreign_keys", []))

        tables.append(
            TableMetadata(
                schema_name=Identifier.from_raw(schema_name_raw, schema_dialect),
                table_name=Identifier.from_raw(tbl["table_name"], schema_dialect),
                columns=columns,
                primary_key=pk,
                foreign_keys=fks,
            )
        )

    return RawSchemaMetadata(
        dialect=schema_dialect,
        schemas=tuple(schemas_seen.values()),
        tables=tuple(tables),
    )


def _default_schema(dialect: SchemaDialect) -> str:
    if dialect == SchemaDialect.SQLITE:
        return "main"
    if dialect == SchemaDialect.MYSQL:
        return "__default__"
    return "public"


def _convert_column(col: dict, ordinal: int, dialect: SchemaDialect) -> ColumnMetadata:
    return ColumnMetadata(
        column_name=Identifier.from_raw(col["column_name"], dialect),
        ordinal_position=ordinal,
        raw_data_type=col["data_type"],
        data_type=col["data_type"],
        nullable=col.get("is_nullable", True),
        default_expression=col.get("default_value"),
        primary_key=col.get("is_primary_key", False),
    )


def _convert_primary_key(pk_cols: list[str], dialect: SchemaDialect) -> PrimaryKeyMetadata | None:
    if not pk_cols:
        return None
    return PrimaryKeyMetadata(
        constrained_columns=tuple(Identifier.from_raw(c, dialect) for c in pk_cols),
    )


def _convert_fk(fk: dict, dialect: SchemaDialect) -> ForeignKeyMetadata:
    constraint_name = fk.get("constraint_name")
    return ForeignKeyMetadata(
        constraint_name=(Identifier.from_raw(constraint_name, dialect) if constraint_name else None),
        constrained_columns=tuple(Identifier.from_raw(c, dialect) for c in fk["constrained_columns"]),
        referred_schema=Identifier.from_raw(fk.get("referred_schema") or _default_schema(dialect), dialect),
        referred_table=Identifier.from_raw(fk["referred_table"], dialect),
        referred_columns=tuple(Identifier.from_raw(c, dialect) for c in fk["referred_columns"]),
    )


# ---------------------------------------------------------------------------
# Save node
# ---------------------------------------------------------------------------


async def save_node(state: AgentState) -> dict:
    """Persist approved Semantic Layer to Metadata Store via semantic_service.

    Input state fields: db_id, user_id, db_type, raw_schema, hitl_approved
    Output state fields: semantic_layer_id | error
    """
    if not state.get("hitl_approved"):
        return {"error": "save_node: HITL not approved, cannot save"}

    raw_schema: RawSchema | None = state.get("raw_schema")
    if not raw_schema or not raw_schema.get("tables"):
        return {"error": "save_node: raw_schema is empty"}

    db_id: int = state["db_id"]
    user_id: int = state["user_id"]
    dialect: str = state.get("db_type", "postgresql")

    try:
        canonical = raw_schema_to_canonical(raw_schema, dialect)
        async for session in get_db_session():
            result = await enrich_and_save_canonical_schema(
                db=session,
                user_id=user_id,
                connection_id=db_id,
                raw_schema=canonical,
                dialect=dialect,
            )
            break

        semantic_layer_id = db_id
        logger.info(
            "Semantic layer saved db_id=%s tables=%d relationships=%d",
            semantic_layer_id,
            len(result.get("tables", [])),
            len(result.get("relationships", [])),
        )
        return {"semantic_layer_id": semantic_layer_id}
    except Exception as exc:
        logger.exception("save_node failed")
        return {"error": f"save_node: {exc}"}
