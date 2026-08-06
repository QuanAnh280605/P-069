"""API integration tests for Live Target DB connection and introspection endpoints."""

import os
import sqlite3
import tempfile

import pytest

from src.api.auth import create_access_token
from src.models.db import UserModel

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
        "dialect": "postgresql",
        "conn_url": conn_url,
    }

    # Connect & Introspect
    res = await client.post(CONNECT_ENDPOINT, json=payload, headers=_token_headers())
    assert res.status_code == 201
    data = res.json()
    assert data["display_name"] == "E-Commerce Live DB"
    assert data["dialect"] == "postgresql"
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
