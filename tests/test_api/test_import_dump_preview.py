"""End-to-end API tests for SQL dump metadata parsing."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import SemanticDatabaseModel, UserModel

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"
ENDPOINT = "/api/v1/semantic/import/preview"


def _auth_headers() -> dict[str, str]:
    user = UserModel(
        id=1,
        email="test@company.com",
        username="tester",
        full_name="Tester",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _upload_headers(filename: str, dialect: str | None = None) -> dict[str, str]:
    headers = _auth_headers() | {"Content-Type": "application/sql", "X-Filename": filename}
    if dialect:
        headers["X-SQL-Dialect"] = dialect
    return headers


@pytest.mark.asyncio
async def test_postgresql_dump_returns_schema_metadata(client) -> None:
    payload = (FIXTURE_ROOT / "postgresql_schema.sql").read_bytes()
    response = await client.post(ENDPOINT, content=payload, headers=_upload_headers("schema.sql"))

    assert response.status_code == 200
    data = response.json()
    assert data["dialect"] == "postgresql"
    assert data["raw_schema"]["contract_version"] == "1.0"
    assert len(data["raw_schema"]["tables"]) == 3
    assert "draft_id" not in data


@pytest.mark.asyncio
async def test_pg_dump_override_returns_complete_core_metadata(client) -> None:
    payload = (FIXTURE_ROOT / "postgresql_dump_schema.sql").read_bytes()
    response = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "postgresql"),
    )

    assert response.status_code == 200
    data = response.json()
    tables = {item["table_name"]["raw_name"]: item for item in data["raw_schema"]["tables"]}
    assert set(tables) == {"users", "categories", "products"}
    assert [item["column_name"]["raw_name"] for item in tables["users"]["columns"]] == [
        "user_id",
        "username",
        "email",
        "password_hash",
        "is_active",
        "created_at",
    ]
    assert [item["column_name"]["raw_name"] for item in tables["categories"]["columns"]] == [
        "category_id",
        "category_name",
        "description",
        "parent_id",
    ]
    assert [item["column_name"]["raw_name"] for item in tables["products"]["columns"]] == [
        "product_id",
        "sku",
        "product_name",
        "category_id",
        "price",
        "stock_quantity",
        "created_at",
    ]
    assert sum(len(item["foreign_keys"]) for item in tables.values()) == 2
    assert all(item["primary_key"] is not None for item in tables.values())


@pytest.mark.asyncio
async def test_upload_does_not_create_semantic_records(client, async_session: AsyncSession) -> None:
    payload = (FIXTURE_ROOT / "mysql_schema.sql").read_bytes()
    before = await _semantic_database_count(async_session)

    response = await client.post(ENDPOINT, content=payload, headers=_upload_headers("schema.sql"))

    assert response.status_code == 200
    assert await _semantic_database_count(async_session) == before


@pytest.mark.asyncio
async def test_row_payload_is_not_returned(client) -> None:
    secret = "preview-secret-value"
    payload = b"INSERT INTO accounts VALUES ('preview-secret-value'); CREATE TABLE accounts (id int);"

    response = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "mysql"),
    )

    assert response.status_code == 200
    assert secret not in response.text
    assert response.json()["diagnostics"][0]["code"] == "DATA_STATEMENTS_IGNORED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "payload", "status_code"),
    [
        ({"Content-Type": "application/json", "X-Filename": "schema.sql"}, b"{}", 415),
        ({"Content-Type": "application/sql", "X-Filename": "schema.txt"}, b"CREATE TABLE x(id int);", 400),
        ({"Content-Type": "application/sql", "X-Filename": "schema.sql"}, b"", 400),
    ],
)
async def test_upload_validation_errors_are_stable(client, headers, payload, status_code) -> None:
    response = await client.post(ENDPOINT, content=payload, headers=_auth_headers() | headers)
    assert response.status_code == status_code


@pytest.mark.asyncio
async def test_parse_error_includes_safe_source_location(client) -> None:
    payload = b"CREATE TABLE x (id int);\nALTER TABLE x ADD COLUMN extra int;"
    response = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "postgresql"),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "DDL_PARSE_ERROR"
    assert (detail["statement_index"], detail["line"], detail["column"]) == (1, 2, 1)


@pytest.mark.asyncio
async def test_preview_requires_authentication(client) -> None:
    response = await client.post(
        ENDPOINT,
        content=b"CREATE TABLE x(id int);",
        headers={"Content-Type": "application/sql", "X-Filename": "schema.sql"},
    )
    assert response.status_code == 401


async def _semantic_database_count(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count()).select_from(SemanticDatabaseModel))
    return int(result or 0)
