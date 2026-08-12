"""Unit tests for Pydantic schemas — CanonicalRelationshipResponse, MetricVersionResponse, MetricWithHistoryResponse, GenerateResponse canonical fields."""

from datetime import UTC, datetime

from src.models.raw_schema import RawSchema
from src.models.schemas import (
    CanonicalRelationshipResponse,
    GenerateResponse,
    MetricResponse,
    MetricVersionResponse,
    MetricWithHistoryResponse,
)


class TestCanonicalRelationshipResponse:
    """Tests for CanonicalRelationshipResponse schema."""

    def test_canonical_relationship_response_fields(self) -> None:
        """CanonicalRelationshipResponse has all required fields from the DB model."""
        now = datetime.now(tz=UTC)
        resp = CanonicalRelationshipResponse(
            id=1,
            connection_id=10,
            from_entity_id=2,
            to_entity_id=3,
            relationship_type="many-to-one",
            join_condition="orders.customer_id = customers.id",
            created_at=now,
        )
        assert resp.id == 1
        assert resp.connection_id == 10
        assert resp.from_entity_id == 2
        assert resp.to_entity_id == 3
        assert resp.relationship_type == "many-to-one"
        assert resp.join_condition == "orders.customer_id = customers.id"
        assert resp.created_at == now

    def test_canonical_relationship_response_missing_field_raises(self) -> None:
        """Missing required fields should raise validation error."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CanonicalRelationshipResponse(
                id=1,
                # missing connection_id, from_entity_id, to_entity_id, etc.
            )


class TestMetricVersionResponse:
    """Tests for MetricVersionResponse schema."""

    def test_metric_version_response_fields(self) -> None:
        """MetricVersionResponse has all required fields from MetricVersionModel."""
        now = datetime.now(tz=UTC)
        resp = MetricVersionResponse(
            id=1,
            metric_id=5,
            version=2,
            formula="SUM(orders.total_amount)",
            changed_by=10,
            change_reason="Updated formula",
            created_at=now,
        )
        assert resp.id == 1
        assert resp.metric_id == 5
        assert resp.version == 2
        assert resp.formula == "SUM(orders.total_amount)"
        assert resp.changed_by == 10
        assert resp.change_reason == "Updated formula"
        assert resp.created_at == now

    def test_metric_version_response_optional_changed_by(self) -> None:
        """changed_by can be None (system-generated version)."""
        now = datetime.now(tz=UTC)
        resp = MetricVersionResponse(
            id=1,
            metric_id=5,
            version=1,
            formula="COUNT(orders.id)",
            changed_by=None,
            change_reason="",
            created_at=now,
        )
        assert resp.changed_by is None


class TestMetricWithHistoryResponse:
    """Tests for MetricWithHistoryResponse schema."""

    def test_metric_with_history_extends_metric_response(self) -> None:
        """MetricWithHistoryResponse extends MetricResponse with version, status, approved_by, history."""
        now = datetime.now(tz=UTC)
        version = MetricVersionResponse(
            id=1,
            metric_id=5,
            version=1,
            formula="COUNT(orders.id)",
            changed_by=None,
            change_reason="",
            created_at=now,
        )
        resp = MetricWithHistoryResponse(
            metric_id=5,
            name="Order Count",
            description="Total orders",
            sql_template="SELECT COUNT(orders.id) FROM orders",
            source="ai",
            version=1,
            status="draft",
            approved_by=None,
            history=[version],
        )
        assert isinstance(resp, MetricResponse)
        assert resp.version == 1
        assert resp.status == "draft"
        assert resp.approved_by is None
        assert len(resp.history) == 1
        assert resp.history[0].formula == "COUNT(orders.id)"

    def test_metric_with_history_empty_history(self) -> None:
        """History defaults to empty list."""
        resp = MetricWithHistoryResponse(
            metric_id=5,
            name="Order Count",
            description="Total orders",
            sql_template="SELECT COUNT(orders.id) FROM orders",
            source="manual",
            version=2,
            status="approved",
            approved_by=3,
            history=[],
        )
        assert resp.history == []
        assert resp.version == 2
        assert resp.status == "approved"
        assert resp.approved_by == 3

    def test_metric_with_history_inherits_metric_response_fields(self) -> None:
        """All MetricResponse fields are still accessible."""
        resp = MetricWithHistoryResponse(
            metric_id=10,
            name="Revenue",
            description="Total revenue",
            sql_template="SELECT SUM(orders.total) FROM orders",
            source="manual",
            version=1,
            status="draft",
            approved_by=None,
        )
        assert resp.metric_id == 10
        assert resp.name == "Revenue"
        assert resp.description == "Total revenue"
        assert resp.sql_template == "SELECT SUM(orders.total) FROM orders"
        assert resp.source == "manual"


class TestGenerateResponseCanonicalFields:
    """Tests for GenerateResponse canonical fields update."""

    def test_generate_response_has_canonical_tables(self) -> None:
        """GenerateResponse should have canonical_tables field."""
        raw_schema: RawSchema = {
            "source": {
                "type": "sql_dump",
                "db_engine": "postgresql",
                "connection_id": None,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        }
        resp = GenerateResponse(
            db_id=1,
            raw_schema=raw_schema,
            enriched_schema={},
            suggested_metrics=[],
            canonical_tables=[{"id": 1, "table_name": "orders", "business_name": "Đơn hàng"}],
        )
        assert len(resp.canonical_tables) == 1
        assert resp.canonical_tables[0]["business_name"] == "Đơn hàng"

    def test_generate_response_has_canonical_relationships(self) -> None:
        """GenerateResponse should have canonical_relationships field."""
        raw_schema: RawSchema = {
            "source": {
                "type": "sql_dump",
                "db_engine": "postgresql",
                "connection_id": None,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        }
        now = datetime.now(tz=UTC)
        rel = CanonicalRelationshipResponse(
            id=1,
            connection_id=10,
            from_entity_id=2,
            to_entity_id=3,
            relationship_type="many-to-one",
            join_condition="orders.customer_id = customers.id",
            created_at=now,
        )
        resp = GenerateResponse(
            db_id=1,
            raw_schema=raw_schema,
            enriched_schema={},
            suggested_metrics=[],
            canonical_relationships=[rel],
        )
        assert len(resp.canonical_relationships) == 1
        assert resp.canonical_relationships[0].relationship_type == "many-to-one"

    def test_generate_response_canonical_fields_default_empty(self) -> None:
        """Canonical fields default to empty lists for backward compatibility."""
        raw_schema: RawSchema = {
            "source": {
                "type": "sql_dump",
                "db_engine": "postgresql",
                "connection_id": None,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        }
        resp = GenerateResponse(
            db_id=1,
            raw_schema=raw_schema,
            enriched_schema={},
            suggested_metrics=[],
        )
        assert resp.canonical_tables == []
        assert resp.canonical_relationships == []

    def test_existing_raw_schema_test_still_passes(self) -> None:
        """Backward compatibility: existing test_raw_schema test should still work."""
        raw_schema: RawSchema = {
            "source": {
                "type": "sql_dump",
                "db_engine": "postgresql",
                "connection_id": None,
                "extracted_at": "2026-08-05T00:00:00Z",
            },
            "tables": [],
            "relationships": [],
        }
        response = GenerateResponse(
            db_id=1,
            raw_schema=raw_schema,
            enriched_schema={},
            suggested_metrics=[],
        )
        assert response.raw_schema["source"]["type"] == "sql_dump"
