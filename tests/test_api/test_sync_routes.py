"""Unit tests for schema sync API endpoints."""

import sqlite3

import pytest
from httpx import AsyncClient

from src.api.auth import create_access_token
from src.models.db import (
    LiveTargetDbModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticTableModel,
    UserModel,
)
from src.services.database import encrypt_conn_url
from src.services.schema_fingerprint import fast_introspect_schema_fingerprint


@pytest.mark.asyncio
async def test_sync_api_endpoints(async_session, client: AsyncClient, tmp_path):
    """Test get sync status, trigger sync, and list sync logs API endpoints."""
    # 1. Setup mock target live DB
    db_file = tmp_path / "sync_api_test.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, age INTEGER)")
    conn.commit()
    conn.close()

    conn_url = f"sqlite:///{db_file}"
    initial_fp = fast_introspect_schema_fingerprint(conn_url, "sqlite")

    sem_db = SemanticDatabaseModel(
        id=501,
        created_by=1,
        display_name="Users DB",
        db_type="sqlite",
        conn_url_enc="semantic:live_target_db:501",
        schema_fingerprint=initial_fp,
        status="approved",
    )
    async_session.add(sem_db)
    await async_session.flush()

    live_db = LiveTargetDbModel(
        id=501,
        created_by=1,
        semantic_db_id=sem_db.id,
        display_name="Users DB",
        dialect="sqlite",
        conn_url_enc=encrypt_conn_url(conn_url),
        schema_metadata={},
    )
    async_session.add(live_db)

    tbl = SemanticTableModel(
        id=601,
        db_id=sem_db.id,
        table_name="users",
        business_name="Người dùng",
        description="Bảng thông tin người dùng",
        created_by=1,
    )
    async_session.add(tbl)
    await async_session.flush()

    col = SemanticColumnModel(
        id=701,
        table_id=tbl.id,
        column_name="email",
        data_type="TEXT",
        business_name="Địa chỉ Email",
        description="Email người dùng",
    )
    async_session.add(col)
    await async_session.commit()

    user = await async_session.get(UserModel, 1)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}

    # 2. Test GET /semantic/{db_id}/sync-status (when in sync)
    res = await client.get(f"/api/v1/semantic/{sem_db.id}/sync-status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["in_sync"] is True
    assert data["semantic_db_id"] == sem_db.id

    # 3. Alter Live DB: rename email -> user_email
    conn = sqlite3.connect(db_file)
    conn.execute("ALTER TABLE users RENAME COLUMN email TO user_email")
    conn.commit()
    conn.close()

    # 4. Check sync status again (should detect drift)
    res_drift = await client.get(f"/api/v1/semantic/{sem_db.id}/sync-status", headers=headers)
    assert res_drift.status_code == 200
    assert res_drift.json()["in_sync"] is False

    # 5. Test POST /semantic/{db_id}/sync (trigger manual sync)
    res_sync = await client.post(f"/api/v1/semantic/{sem_db.id}/sync", headers=headers)
    assert res_sync.status_code == 200
    sync_data = res_sync.json()
    assert sync_data["status"] == "healed"

    # 6. Test GET /semantic/{db_id}/sync-logs
    res_logs = await client.get(f"/api/v1/semantic/{sem_db.id}/sync-logs", headers=headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) >= 1
    assert logs[0]["status"] == "healed"
