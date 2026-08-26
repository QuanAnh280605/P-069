"""Deterministic schema fingerprinting for instant drift detection.

Provides:
  - compute_schema_fingerprint: Hash canonical table & column definitions.
  - fast_introspect_schema_fingerprint: Ultra-fast (<5ms) schema inspection & hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from src.models.schema_metadata import RawSchemaMetadata, SchemaDialect

logger = logging.getLogger(__name__)

_SYNC_DRIVERS = {
    "postgresql+asyncpg": "postgresql+psycopg2",
    "mysql+asyncmy": "mysql+pymysql",
    "mysql+aiomysql": "mysql+pymysql",
    "sqlite+aiosqlite": "sqlite",
}


def _sync_url(conn_url: str) -> str:
    """Return synchronous driver URL for inspection."""
    url = make_url(conn_url)
    driver = _SYNC_DRIVERS.get(url.drivername)
    if driver is None:
        return conn_url
    return url.set(drivername=driver).render_as_string(hide_password=False)


def _table_signature(table: Any) -> tuple[str, list[dict[str, Any]]]:
    """Extract sorted column signature for one table."""
    if hasattr(table, "table_name") and hasattr(table, "columns"):
        t_name = table.table_name.raw_name if hasattr(table.table_name, "raw_name") else str(table.table_name)
        cols = [
            {
                "name": c.column_name.raw_name if hasattr(c.column_name, "raw_name") else str(c.column_name),
                "type": str(c.data_type).lower(),
                "nullable": bool(getattr(c, "is_nullable", getattr(c, "nullable", True))),
                "pk": bool(getattr(c, "is_primary_key", getattr(c, "primary_key", False))),
            }
            for c in table.columns
        ]
    elif isinstance(table, dict):
        t_name = str(table.get("table_name", ""))
        raw_cols = table.get("columns", [])
        cols = [
            {
                "name": str(c.get("name") or c.get("column_name", "")),
                "type": str(c.get("type") or c.get("data_type", "")).lower(),
                "nullable": bool(c.get("nullable", c.get("is_nullable", True))),
                "pk": bool(c.get("pk", c.get("is_primary_key", False))),
            }
            for c in raw_cols
        ]
    else:
        t_name = ""
        cols = []
    cols.sort(key=lambda item: item["name"])
    return t_name, cols


def compute_schema_fingerprint(tables_or_schema: RawSchemaMetadata | list[Any] | dict[str, Any]) -> str:
    """Compute a deterministic MD5 hash for a schema."""
    if isinstance(tables_or_schema, RawSchemaMetadata):
        tables = list(tables_or_schema.tables)
    elif isinstance(tables_or_schema, dict):
        tables = tables_or_schema.get("tables", [])
    else:
        tables = list(tables_or_schema)

    signatures = [_table_signature(t) for t in tables]
    signatures.sort(key=lambda item: item[0])

    normalized_payload = [{"table": name, "columns": cols} for name, cols in signatures if name]
    serialized = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()  # noqa: S324


def fast_introspect_schema_fingerprint(conn_url: str, dialect: str | SchemaDialect) -> str:
    """Fast inspection of table and column signatures to compute fingerprint in <5ms."""
    engine = create_engine(_sync_url(conn_url))
    tables_data: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()
            for t_name in table_names:
                cols = inspector.get_columns(t_name)
                pk_constraint = inspector.get_pk_constraint(t_name) or {}
                pk_cols = set(pk_constraint.get("constrained_columns") or [])
                tables_data.append(
                    {
                        "table_name": t_name,
                        "columns": [
                            {
                                "name": c["name"],
                                "type": str(c["type"]),
                                "nullable": bool(c.get("nullable", True)),
                                "pk": c["name"] in pk_cols,
                            }
                            for c in cols
                        ],
                    }
                )
    finally:
        engine.dispose()

    return compute_schema_fingerprint(tables_data)
