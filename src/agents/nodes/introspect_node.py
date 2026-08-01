"""Introspect Node — Flow 1 Step 1.

Kết nối Target DB qua Fernet-decrypted URL, dùng SQLAlchemy Inspector
để đọc schema metadata (tên bảng, cột, FK, kiểu dữ liệu).
KHÔNG thực thi bất kỳ câu truy vấn SELECT data nào.
"""
from __future__ import annotations

from src.agents.state import AgentState


async def introspect_node(state: AgentState) -> dict:
    """Read schema metadata from Target DB using SQLAlchemy Inspector.

    Input state fields: conn_url_enc, db_id
    Output state fields: raw_schema | error
    """
    # TODO: Implement steps:
    # 1. Decrypt conn_url_enc with Fernet key from settings
    # 2. Create SQLAlchemy engine (no execute, schema only)
    # 3. Use Inspector.get_table_names(), get_columns(), get_foreign_keys()
    # 4. Build raw_schema dict and return
    return {
        "raw_schema": {},
        "error": "introspect_node: not yet implemented",
    }
