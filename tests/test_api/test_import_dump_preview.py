"""End-to-end API tests for the non-persistent SQL dump preview."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.models.db import SemanticDatabaseModel, UserModel
from src.services.preview_draft_store import get_preview_draft_store

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"
ENDPOINT = "/api/v1/semantic/import/preview"


def _auth_headers(user_id: int = 1) -> dict[str, str]:
    user = UserModel(
        id=user_id,
        email=f"user{user_id}@company.com",
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        hashed_password="hash",
        role="admin",
        status="active",
    )
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _upload_headers(filename: str, dialect: str | None = None) -> dict[str, str]:
    headers = _auth_headers()
    headers.update({"Content-Type": "application/sql", "X-Filename": filename})
    if dialect:
        headers["X-SQL-Dialect"] = dialect
    return headers


@pytest_asyncio.fixture(autouse=True)
async def _isolated_preview_store():
    get_preview_draft_store.cache_clear()
    yield
    await get_preview_draft_store().clear()
    get_preview_draft_store.cache_clear()


@pytest.mark.asyncio
async def test_real_postgresql_dump_upload_returns_pending_review(client) -> None:
    payload = (FIXTURE_ROOT / "postgresql_schema.sql").read_bytes()

    response = await client.post(ENDPOINT, content=payload, headers=_upload_headers("schema.sql"))

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending_review"
    assert data["persistence"] == "none"
    assert data["dialect"] == "postgresql"
    assert len(data["raw_schema"]["tables"]) == 3
    assert len(data["draft_id"]) >= 20


@pytest.mark.asyncio
async def test_pg_dump_with_owner_and_sequence_defaults_returns_preview(client) -> None:
    payload = (FIXTURE_ROOT / "postgresql_dump_schema.sql").read_bytes()

    response = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "postgresql"),
    )

    assert response.status_code == 202
    data = response.json()
    assert len(data["raw_schema"]["tables"]) == 3
    assert any(item["message"] == "Object ownership statement was ignored" for item in data["diagnostics"])


@pytest.mark.asyncio
async def test_upload_review_and_approve_never_create_semantic_records(
    client,
    async_session: AsyncSession,
) -> None:
    payload = (FIXTURE_ROOT / "mysql_schema.sql").read_bytes()
    before = await _semantic_database_count(async_session)

    upload = await client.post(ENDPOINT, content=payload, headers=_upload_headers("schema.sql"))
    draft_id = upload.json()["draft_id"]
    review = await client.get(f"/api/v1/semantic/import/drafts/{draft_id}", headers=_auth_headers())
    approval = await client.post(
        f"/api/v1/semantic/import/drafts/{draft_id}/approve",
        headers=_auth_headers(),
    )

    assert review.status_code == 200
    assert approval.status_code == 200
    assert approval.json()["draft"]["status"] == "approved_preview"
    assert approval.json()["draft"]["persistence"] == "none"
    assert await _semantic_database_count(async_session) == before


@pytest.mark.asyncio
async def test_preview_draft_is_hidden_from_another_owner(client, async_session: AsyncSession) -> None:
    payload = b"CREATE TABLE public.accounts (id integer PRIMARY KEY);"
    upload = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "postgresql"),
    )
    second_user = await _create_second_user(async_session)

    response = await client.get(
        f"/api/v1/semantic/import/drafts/{upload.json()['draft_id']}",
        headers=_auth_headers(second_user.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_row_payload_is_not_returned_or_persisted_in_preview(client) -> None:
    secret = "preview-secret-value"
    template = "INSERT INTO accounts VALUES ('__SECRET__'); CREATE TABLE accounts (id int);"
    payload = template.replace("__SECRET__", secret).encode()

    response = await client.post(
        ENDPOINT,
        content=payload,
        headers=_upload_headers("schema.sql", "mysql"),
    )

    assert response.status_code == 202
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
    assert response.json()["detail"] == {
        "code": "DDL_PARSE_ERROR",
        "message": "ALTER TABLE changes unsupported core metadata",
        "statement_index": 1,
        "line": 2,
        "column": 1,
    }


@pytest.mark.asyncio
async def test_preview_requires_authentication(client) -> None:
    response = await client.post(
        ENDPOINT,
        content=b"CREATE TABLE x(id int);",
        headers={"Content-Type": "application/sql", "X-Filename": "schema.sql"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preview_is_always_disabled_in_production(client, monkeypatch) -> None:
    settings = SimpleNamespace(sql_dump_preview_enabled=True, app_env="production")
    monkeypatch.setattr("src.api.routes.get_settings", lambda: settings)

    response = await client.post(
        ENDPOINT,
        content=b"CREATE TABLE x(id int);",
        headers=_upload_headers("schema.sql", "postgresql"),
    )

    assert response.status_code == 404


async def _semantic_database_count(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count()).select_from(SemanticDatabaseModel))
    return int(result or 0)


async def _create_second_user(session: AsyncSession) -> UserModel:
    user = UserModel(
        id=2,
        email="second@company.com",
        username="second",
        full_name="Second User",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    session.add(user)
    await session.commit()
    return user
