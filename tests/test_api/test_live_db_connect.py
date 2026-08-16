"""API integration tests for Live Target DB connection and introspection endpoints."""

import os
import sqlite3
import tempfile

import pytest

from src.api.auth import create_access_token
from src.models.db import LiveTargetDbModel, UserModel

CONNECT_ENDPOINT = "/api/v1/semantic/db/connect"
SAVED_DB_ENDPOINT = "/api/v1/semantic/db/saved"


def _token_headers(user: UserModel | None = None) -> dict[str, str]:
    active_user = user or UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    return {"Authorization": f"Bearer {create_access_token(active_user)}"}


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database for testing live connection endpoint."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE products (product_id INT PRIMARY KEY, title TEXT);")
    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_live_db_connect_endpoint_lifecycle(client, temp_sqlite_db: str):
    """Test POST /semantic/db/connect and GET/DELETE endpoints."""
    conn_url = f"sqlite:///{temp_sqlite_db}"
    payload = {
        "display_name": "  E-Commerce Live DB  ",
        "dialect": "sqlite",
        "conn_url": conn_url,
    }

    # Connect & Introspect
    res = await client.post(CONNECT_ENDPOINT, json=payload, headers=_token_headers())
    assert res.status_code == 201
    data = res.json()
    assert data["display_name"] == "E-Commerce Live DB"
    assert data["dialect"] == "sqlite"
    assert data["table_count"] == 1
    db_id = data["id"]

    # List saved live dbs
    list_res = await client.get(SAVED_DB_ENDPOINT, headers=_token_headers())
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == db_id

    # Get single live db detail
    detail_res = await client.get(f"{SAVED_DB_ENDPOINT}/{db_id}", headers=_token_headers())
    assert detail_res.status_code == 200
    assert detail_res.json()["display_name"] == "E-Commerce Live DB"

    # Delete live db
    del_res = await client.delete(f"{SAVED_DB_ENDPOINT}/{db_id}", headers=_token_headers())
    assert del_res.status_code == 204

    # Verify deleted
    get_after = await client.get(f"{SAVED_DB_ENDPOINT}/{db_id}", headers=_token_headers())
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_live_db_connect_auto_detect_and_mismatch(client, temp_sqlite_db: str):
    """Test POST /semantic/db/connect with auto-detect and strict mismatch validation."""
    conn_url = f"sqlite:///{temp_sqlite_db}"

    # Auto detect test
    auto_payload = {
        "display_name": "Auto Detect Store",
        "dialect": "auto",
        "conn_url": conn_url,
    }
    res_auto = await client.post(CONNECT_ENDPOINT, json=auto_payload, headers=_token_headers())
    assert res_auto.status_code == 201
    assert res_auto.json()["dialect"] == "sqlite"

    # Mismatched dialect test
    mismatch_payload = {
        "display_name": "Mismatch DB",
        "dialect": "mysql",
        "conn_url": conn_url,
    }
    res_mismatch = await client.post(CONNECT_ENDPOINT, json=mismatch_payload, headers=_token_headers())
    assert res_mismatch.status_code == 400
    assert "does not match selected dialect" in res_mismatch.json()["detail"]


@pytest.mark.asyncio
async def test_saved_dbs_empty_list_returns_200(client):
    """GET /semantic/db/saved returns 200 and empty list when user has no databases."""
    res = await client.get(SAVED_DB_ENDPOINT, headers=_token_headers())
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_saved_dbs_handles_empty_or_corrupted_metadata(client, async_session):
    """GET /semantic/db/saved returns 200 without 500 error even if metadata is empty dict or string."""
    live_db = LiveTargetDbModel(
        created_by=1,
        display_name="Corrupted Meta DB",
        dialect="sqlite",
        conn_url_enc="dummy-enc",
        schema_metadata={},
    )
    async_session.add(live_db)
    await async_session.commit()

    res = await client.get(SAVED_DB_ENDPOINT, headers=_token_headers())
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    target = next((item for item in items if item["display_name"] == "Corrupted Meta DB"), None)
    assert target is not None
    assert target["table_count"] == 0

    # Test single item detail handles empty metadata safely too
    detail_res = await client.get(f"{SAVED_DB_ENDPOINT}/{live_db.id}", headers=_token_headers())
    assert detail_res.status_code == 200
    assert detail_res.json()["table_count"] == 0


def test_live_db_introspect_samples_categorical_columns(temp_sqlite_db: str) -> None:
    """Test that introspect_live_database samples categorical and flag columns."""
    from src.models.schema_metadata import SchemaDialect
    from src.services.live_db_service import introspect_live_database

    conn = sqlite3.connect(temp_sqlite_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE orders (id INT PRIMARY KEY, is_completed VARCHAR(1), status VARCHAR(20));")
    cursor.execute("INSERT INTO orders VALUES (1, '1', 'Completed'), (2, '0', 'Pending'), (3, '1', 'Completed');")
    conn.commit()
    conn.close()

    raw_schema = introspect_live_database(f"sqlite:///{temp_sqlite_db}", SchemaDialect.SQLITE)
    orders_table = next(t for t in raw_schema.tables if t.table_name.raw_name == "orders")
    is_completed_col = next(c for c in orders_table.columns if c.column_name.raw_name == "is_completed")
    status_col = next(c for c in orders_table.columns if c.column_name.raw_name == "status")

    assert is_completed_col.sample_values is not None
    assert set(is_completed_col.sample_values) == {"0", "1"}
    assert status_col.sample_values is not None
    assert set(status_col.sample_values) == {"Completed", "Pending"}
