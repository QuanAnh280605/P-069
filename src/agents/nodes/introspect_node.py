"""Introspect Node — Flow 1 Step 1.

Kết nối Target DB qua Fernet-decrypted URL, dùng SQLAlchemy Inspector
để đọc schema metadata (tên bảng, cột, FK, kiểu dữ liệu).
KHÔNG thực thi bất kỳ câu truy vấn SELECT data nào.
"""

from __future__ import annotations

from src.agents.state import AgentState
from src.models.schema_metadata import SchemaDialect
from src.services.database import decrypt_conn_url
from src.services.live_db_service import introspect_live_database


async def introspect_node(state: AgentState) -> dict:
    """Read schema metadata from Target DB using SQLAlchemy Inspector.

    Input state fields: conn_url_enc | conn_url, dialect
    Output state fields: raw_schema | error
    """
    conn_url = state.get("conn_url")
    conn_url_enc = state.get("conn_url_enc")
    if not conn_url and conn_url_enc:
        try:
            conn_url = decrypt_conn_url(conn_url_enc)
        except Exception as exc:
            return {"raw_schema": {}, "error": f"Failed to decrypt connection URL: {exc}"}

    if not conn_url:
        return {"raw_schema": {}, "error": "Missing connection URL for introspection"}

    dialect_str = state.get("dialect", "postgresql")
    try:
        dialect = SchemaDialect(dialect_str)
        raw_schema = introspect_live_database(conn_url, dialect)
        return {"raw_schema": raw_schema.model_dump(mode="json"), "error": ""}
    except Exception as exc:
        return {"raw_schema": {}, "error": f"Schema introspection failed: {exc}"}
