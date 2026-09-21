"""API tests for YAML preview and JSON metric persistence."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token
from src.api.routes import _discover_candidate_dimensions_for_query
from src.models.db import (
    CanonicalRelationshipModel,
    OrganizationMemberModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.metric_definition import MetricDefinition
from src.models.review_mixin import REVIEW_STATUS_APPROVED
from src.models.schemas import DuplicateMetricNotice, MetricSuggestionItem
from src.services.metric_context import MetricContextResult
from src.services.metrics import (
    MetricGenerationInvalidError,
    MetricGenerationTimeoutError,
    MetricGenerationUnavailableError,
)
from src.services.organization_service import create_organization


def _headers_for(user: UserModel, org_id: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    if org_id is not None:
        headers["X-Organization-ID"] = str(org_id)
    return headers


async def _seed_workspace_db(async_session: AsyncSession, role: str) -> tuple[UserModel, int, int]:
    """Seed an org-scoped Semantic DB and return (actor_user, org_id, db_id)."""
    owner = await async_session.get(UserModel, 1)
    organization = await create_organization(async_session, owner.id, f"{role} Workspace", f"jp-{role}")
    if role == "admin":
        actor = owner
    else:
        actor = UserModel(
            id=2,
            email=f"{role}@company.com",
            username=role,
            full_name=role.replace("_", " ").title(),
            hashed_password="hash",
            status="active",
        )
        async_session.add(actor)
        async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=actor.id, role=role))
    database = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=owner.id,
        display_name="Join Path WS DB",
        db_type="postgresql",
        conn_url_enc="enc",
        status="saved",
    )
    async_session.add(database)
    await async_session.commit()
    return actor, organization.id, database.id


@pytest.fixture
def auth_headers() -> dict[str, str]:
    user = UserModel(id=1, email="test@company.com", username="tester", hashed_password="hash")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _definition(name: str = "Doanh thu") -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "metric": {
                "name": name,
                "formula": {"function": "SUM", "expression": "quantity * unit_price"},
                "base_entity": "order_items",
                "filters": [],
                "status": "pending_approval",
                "confidence": "high",
                "excluded_notes": "Chưa trừ hoàn tiền",
            }
        }
    )


async def _seed_store_dimension(async_session: AsyncSession) -> int:
    """Seed one display-name dimension and return its semantic database id."""
    database = SemanticDatabaseModel(
        created_by=1,
        display_name="First metric DB",
        db_type="sqlite",
        conn_url_enc="enc",
    )
    async_session.add(database)
    await async_session.flush()
    stores = SemanticTableModel(
        db_id=database.id,
        table_name="stores",
        business_name="Cửa hàng",
        created_by=1,
    )
    async_session.add(stores)
    await async_session.flush()
    async_session.add(
        SemanticColumnModel(
            table_id=stores.id,
            column_name="store_name",
            data_type="VARCHAR",
            business_name="Tên cửa hàng",
        )
    )
    await async_session.flush()

    return database.id


@pytest.mark.asyncio
async def test_dimension_discovery_works_before_first_metric(async_session: AsyncSession) -> None:
    """Metric creation can resolve display names when the catalog is still empty."""
    db_id = await _seed_store_dimension(async_session)

    candidates, _ = await _discover_candidate_dimensions_for_query(
        async_session, db_id, {"metrics": []}, "Tạo metric doanh thu theo cửa hàng"
    )

    assert any(item["column_name"] == "store_name" for item in candidates)


async def _seed(async_session: AsyncSession, db_id: int) -> None:
    database = SemanticDatabaseModel(
        id=db_id,
        created_by=1,
        display_name="Retail",
        db_type="postgresql",
        conn_url_enc="enc",
        status="saved",
    )
    table = SemanticTableModel(
        id=db_id, db_id=db_id, table_name="order_items", business_name="Chi tiết đơn", description=""
    )
    async_session.add_all([database, table])
    await async_session.flush()
    async_session.add_all(
        [
            SemanticColumnModel(
                table_id=table.id, column_name="quantity", data_type="INTEGER", business_name="Số lượng"
            ),
            SemanticColumnModel(
                table_id=table.id, column_name="unit_price", data_type="NUMERIC", business_name="Đơn giá"
            ),
        ]
    )
    await async_session.commit()


@pytest.mark.asyncio
@patch("src.api.routes.fast_metric_context")
@patch("src.api.routes.generate_metrics_from_prompt")
async def test_generate_returns_yaml_without_persisting(
    mock_generate: object,
    mock_context: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    await _seed(async_session, 10)
    mock_context.return_value = MetricContextResult(
        schema={"tables": [{"table_name": "order_items", "columns": []}], "relationships": []},
        diagnostic={"status": "ready"},
    )
    definition = _definition()
    mock_generate.return_value = ([MetricSuggestionItem(definition=definition, yaml_preview=definition.to_yaml())], [])
    response = await client.post(
        "/api/v1/semantic/10/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestions"][0]
    assert suggestion["definition"]["metric"]["name"] == "Doanh thu"
    assert "metric:" in suggestion["yaml_preview"]
    assert (await async_session.get(SemanticMetricModel, 1)) is None


@pytest.mark.asyncio
@patch("src.api.routes.fast_metric_context")
@patch("src.api.routes.generate_metrics_from_prompt")
async def test_generate_returns_duplicates_in_response(
    mock_generate: AsyncMock,
    mock_context: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    await _seed(async_session, 10)
    mock_context.return_value = MetricContextResult(
        schema={"tables": [{"table_name": "order_items", "columns": []}], "relationships": []},
        diagnostic={"status": "ready"},
    )
    mock_generate.return_value = (
        [],
        [
            DuplicateMetricNotice(
                existing_metric_id=12,
                existing_metric_name="Doanh thu",
                existing_metric_status="approved",
                user_message="Đã tồn tại metric chuẩn",
            )
        ],
    )
    response = await client.post(
        "/api/v1/semantic/10/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["duplicates"]) == 1
    assert body["duplicates"][0]["user_message"] == "Đã tồn tại metric chuẩn"
    assert body["dedupe_performed"] is True
    assert body["suggestions"] == []


@pytest.mark.asyncio
@patch("src.api.routes.fast_metric_context")
@patch("src.api.routes.generate_metrics_from_prompt")
@patch("src.api.routes.load_existing_for_dedupe", new_callable=AsyncMock)
async def test_generate_dedupe_unavailable_flag(
    mock_load: AsyncMock,
    mock_generate: AsyncMock,
    mock_context: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    await _seed(async_session, 10)
    mock_load.return_value = ([], False)
    mock_context.return_value = MetricContextResult(
        schema={"tables": [{"table_name": "order_items", "columns": []}], "relationships": []},
        diagnostic={"status": "ready"},
    )
    mock_generate.return_value = ([], [])
    response = await client.post(
        "/api/v1/semantic/10/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["dedupe_performed"] is False
    mock_generate.assert_awaited_once()
    assert mock_generate.call_args.kwargs.get("existing_metrics") is None


@pytest.mark.asyncio
@patch("src.api.routes.fast_metric_context")
@patch("src.services.metrics.generate_definitions_v2", new_callable=AsyncMock)
async def test_generate_endpoint_regression_returns_single_suggestion(
    mock_generate: AsyncMock,
    mock_context: AsyncMock,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    await _seed(async_session, 50)
    mock_context.return_value = MetricContextResult(
        schema={
            "tables": [
                {
                    "table_name": "order_items",
                    "columns": [
                        {"column_name": "quantity", "data_type": "INTEGER"},
                        {"column_name": "unit_price", "data_type": "NUMERIC"},
                    ],
                }
            ]
        },
        diagnostic={"status": "ready"},
    )
    defs = [_definition("Doanh thu"), _definition("Số lượng"), _definition("Giá trị")]
    mock_generate.return_value = (defs, [], [])
    response = await client.post(
        "/api/v1/semantic/50/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()["suggestions"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status"),
    (
        (MetricGenerationTimeoutError("slow"), 504),
        (MetricGenerationInvalidError("bad output"), 502),
        (MetricGenerationUnavailableError("down"), 502),
    ),
)
@patch("src.api.routes.fast_metric_context")
@patch("src.api.routes.generate_metrics_from_prompt")
async def test_generate_maps_metric_llm_failures(
    mock_generate: AsyncMock,
    mock_context: AsyncMock,
    failure: Exception,
    expected_status: int,
    client: AsyncClient,
    async_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """The direct generation API exposes timeout and invalid-upstream failures."""
    await _seed(async_session, 51)
    mock_context.return_value = MetricContextResult(
        schema={"tables": [{"table_name": "order_items", "columns": []}], "relationships": []},
        diagnostic={"status": "ready"},
    )
    mock_generate.side_effect = failure

    response = await client.post(
        "/api/v1/semantic/51/metrics/generate", json={"prompt": "Tính doanh thu"}, headers=auth_headers
    )

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_create_update_and_delete_definition(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    await _seed(async_session, 20)
    payload = {"definition": _definition().model_dump(mode="json"), "source": "ai"}
    created = await client.post("/api/v1/semantic/20/metric", json=payload, headers=auth_headers)
    assert created.status_code == 201
    metric_id = created.json()["metric_id"]
    stored = await async_session.get(SemanticMetricModel, metric_id)
    assert stored.definition["metric"]["formula"]["expression"] == "quantity * unit_price"
    assert stored.sql_template == ""
    updated_payload = {"definition": _definition("Doanh thu thuần").model_dump(mode="json")}
    updated = await client.put(f"/api/v1/semantic/20/metric/{metric_id}", json=updated_payload, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["definition"]["metric"]["name"] == "Doanh thu thuần"
    deleted = await client.delete(f"/api/v1/semantic/20/metric/{metric_id}", headers=auth_headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_create_rejects_sql_contract(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/semantic/1/metric",
        json={"name": "Bad", "sql_template": "SELECT 1", "source": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_join_path_options_endpoint(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    database = SemanticDatabaseModel(
        id=30, created_by=1, display_name="Retail", db_type="postgresql", conn_url_enc="enc", status="saved"
    )
    base = SemanticTableModel(id=30, db_id=30, table_name="orders", business_name="Đơn", description="")
    target = SemanticTableModel(id=31, db_id=30, table_name="products", business_name="SP", description="")
    async_session.add_all([database, base, target])
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            id=301,
            connection_id=30,
            from_entity_id=base.id,
            to_entity_id=target.id,
            relationship_type="many_to_one",
            join_condition="orders.product_id = products.id",
            business_name="Sản phẩm",
            description="order to product",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[],
        )
    )
    await async_session.commit()

    response = await client.get("/api/v1/semantic/30/metric/join-path-options?base_entity_id=30", headers=auth_headers)
    assert response.status_code == 200
    options = response.json()
    assert "31" in options
    opt = options["31"][0]
    assert opt["relationship_ids"] == [301]
    assert opt["entity_ids"] == [30, 31]
    assert opt["labels"] == ["Sản phẩm"]
    assert opt["descriptions"] == ["order to product"]


@pytest.mark.asyncio
async def test_join_path_options_workspace_data_lead_allowed(client: AsyncClient, async_session: AsyncSession) -> None:
    actor, org_id, db_id = await _seed_workspace_db(async_session, "data_lead")
    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/join-path-options?base_entity_id=1",
        headers=_headers_for(actor, org_id),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_join_path_options_workspace_member_allowed(client: AsyncClient, async_session: AsyncSession) -> None:
    actor, org_id, db_id = await _seed_workspace_db(async_session, "member")
    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/join-path-options?base_entity_id=1",
        headers=_headers_for(actor, org_id),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_join_path_options_workspace_admin_forbidden(client: AsyncClient, async_session: AsyncSession) -> None:
    actor, org_id, db_id = await _seed_workspace_db(async_session, "admin")
    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/join-path-options?base_entity_id=1",
        headers=_headers_for(actor, org_id),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_join_path_options_cross_org_masked(client: AsyncClient, async_session: AsyncSession) -> None:
    _, org_a, db_id = await _seed_workspace_db(async_session, "member")
    owner = await async_session.get(UserModel, 1)
    org_b = await create_organization(async_session, owner.id, "Other Workspace", "jp-other")
    response = await client.get(
        f"/api/v1/semantic/{db_id}/metric/join-path-options?base_entity_id=1",
        headers=_headers_for(owner, org_b.id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_join_path_options_personal_creator_allowed(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    database = SemanticDatabaseModel(
        org_id=None, created_by=1, display_name="Personal", db_type="postgresql", conn_url_enc="enc", status="saved"
    )
    async_session.add(database)
    await async_session.commit()
    response = await client.get(
        f"/api/v1/semantic/{database.id}/metric/join-path-options?base_entity_id=1", headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_join_path_options_personal_non_owner_masked(client: AsyncClient, async_session: AsyncSession) -> None:
    database = SemanticDatabaseModel(
        org_id=None, created_by=1, display_name="Personal", db_type="postgresql", conn_url_enc="enc", status="saved"
    )
    async_session.add(database)
    other = UserModel(
        id=2, email="other@company.com", username="other", full_name="Other", hashed_password="hash", status="active"
    )
    async_session.add(other)
    await async_session.commit()
    response = await client.get(
        f"/api/v1/semantic/{database.id}/metric/join-path-options?base_entity_id=1",
        headers=_headers_for(other),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_metric_persists_preferred_join_paths(
    client: AsyncClient, async_session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    await _seed(async_session, 40)
    products = SemanticTableModel(id=41, db_id=40, table_name="products", business_name="SP", description="")
    async_session.add(products)
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            id=401,
            connection_id=40,
            from_entity_id=40,
            to_entity_id=41,
            relationship_type="many_to_one",
            join_condition="order_items.product_id = products.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[],
        )
    )
    await async_session.commit()
    definition = _definition()
    definition.metric.preferred_join_paths = {41: [401]}
    payload = {"definition": definition.model_dump(mode="json"), "source": "ai"}
    created = await client.post("/api/v1/semantic/40/metric", json=payload, headers=auth_headers)
    assert created.status_code == 201
    assert created.json()["definition"]["metric"]["preferred_join_paths"] == {"41": [401]}
    metric_id = created.json()["metric_id"]
    stored = await async_session.get(SemanticMetricModel, metric_id)
    assert stored.definition["metric"]["preferred_join_paths"] == {"41": [401]}
    # Re-validating the stored definition coerces JSON string keys back to ints.
    from src.models.metric_definition import MetricDefinition

    reloaded = MetricDefinition.model_validate(stored.definition)
    assert reloaded.metric.preferred_join_paths == {41: [401]}


async def _seed_tables(async_session: AsyncSession, db_id: int) -> None:
    table = SemanticTableModel(
        id=db_id + 100, db_id=db_id, table_name="order_items", business_name="Chi tiết đơn", description=""
    )
    async_session.add(table)
    await async_session.flush()
    async_session.add_all(
        [
            SemanticColumnModel(
                table_id=table.id, column_name="quantity", data_type="INTEGER", business_name="Số lượng"
            ),
            SemanticColumnModel(
                table_id=table.id, column_name="unit_price", data_type="NUMERIC", business_name="Đơn giá"
            ),
        ]
    )
    await async_session.commit()
