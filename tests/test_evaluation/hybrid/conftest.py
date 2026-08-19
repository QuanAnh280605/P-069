"""Shared fixtures: a minimal in-code DomainDataset for hybrid engine tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.dataset.loader import DomainDataset
from eval.dataset.models import (
    CanonicalDimensionDefinition,
    CanonicalEntityDefinition,
    CanonicalMetricDefinition,
    CanonicalRelationshipDefinition,
    DiscoveryCase,
    DiscoveryCaseExpected,
    DomainManifest,
    GuardrailCase,
    GuardrailExpected,
    ManifestCaseFiles,
    MetricDefinitionCase,
    MetricDefinitionCaseContext,
    QueryCase,
    QueryCaseExpected,
)

FROZEN = datetime(2026, 8, 1, tzinfo=UTC)


def _manifest() -> DomainManifest:
    return DomainManifest(
        dataset_version="1.0.0",
        contract_version="2.0.0",
        domain="mini",
        supported_dialects=["sqlite"],
        execution_dialect="sqlite",
        review_status="approved",
        approved_by=["expert"],
        reviewed_at=FROZEN,
        frozen_evaluation_date=FROZEN,
        ground_truth_source="mini",
        ground_truth_metric_count=1,
        case_files=ManifestCaseFiles(
            discovery="discovery.json",
            metric_definition="metrics.json",
            query="queries.json",
            guardrail="guardrails.json",
        ),
    )


def _column(name: str, primary: bool = False, data_type: str = "TEXT", foreign_key: bool = False) -> dict:
    return {
        "column_name": name,
        "data_type": data_type,
        "is_nullable": not primary,
        "is_primary_key": primary,
        "is_foreign_key": foreign_key,
        "default_value": None,
        "sample_values": None,
        "references": None,
    }


def _table(name: str, columns: list[dict], primary_keys: list[str]) -> dict:
    return {
        "table_name": name,
        "schema_name": None,
        "table_type": "BASE TABLE",
        "row_count_estimate": None,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": [],
        "indexes": [],
    }


def _raw_schema() -> dict:
    return {
        "source": {
            "type": "sql_dump",
            "db_engine": "sqlite",
            "connection_id": None,
            "extracted_at": "2026-08-01T00:00:00+00:00",
        },
        "tables": [
            _table(
                "orders",
                [
                    _column("id", primary=True, data_type="INTEGER"),
                    _column("amount"),
                    _column("customer_id", foreign_key=True),
                ],
                ["id"],
            ),
            _table(
                "customers",
                [_column("id", primary=True, data_type="INTEGER"), _column("name")],
                ["id"],
            ),
        ],
        "relationships": [
            {
                "from_table": "orders",
                "from_column": "customer_id",
                "to_table": "customers",
                "to_column": "id",
                "relationship_type": "many_to_one",
            }
        ],
    }


def _canonical_entities() -> dict[str, CanonicalEntityDefinition]:
    dimension = CanonicalDimensionDefinition(
        name="order_amount", business_name="Giá trị đơn hàng", type="number", field="amount"
    )
    relationship = CanonicalRelationshipDefinition(
        target_entity="customers",
        relation_type="BELONGS_TO",
        join_condition="orders.customer_id = customers.id",
    )
    entity = CanonicalEntityDefinition(
        entity="orders",
        table_mapping="orders",
        business_name="Đơn hàng",
        dimensions=[dimension],
        relationships=[relationship],
    )
    return {"orders": entity}


def _canonical_metrics() -> dict[str, CanonicalMetricDefinition]:
    metric = CanonicalMetricDefinition(
        metric="total_revenue",
        business_name="Tổng doanh thu",
        domain="mini",
        metric_type="simple",
        target_entity="orders",
        source_table="orders",
        aggregation="sum",
        field="amount",
        business_formula="SUM(order_amount)",
        sql_expression="SUM(amount)",
        allowed_dimensions=["order_month"],
        default_time_grain="month",
        reference_source="mini",
        status="approved",
        owner="expert",
        ground_truth_source="mini",
    )
    return {"total_revenue": metric}


def _discovery_case() -> DiscoveryCase:
    return DiscoveryCase(
        case_id="disc_001",
        source_type="sql_dump",
        dialect="sqlite",
        raw_schema_ref="mini_schema",
        expected=DiscoveryCaseExpected(
            entity_refs=["canonical/orders.yaml"],
            relationship_expectations=[
                {
                    "source_entity": "orders",
                    "source_field": "customer_id",
                    "target_entity": "customers",
                    "target_field": "id",
                    "relation_type": "BELONGS_TO",
                }
            ],
        ),
        tags=["mini", "sql_dump"],
    )


def _metric_case() -> MetricDefinitionCase:
    return MetricDefinitionCase(
        case_id="metric_001",
        request="Tổng doanh thu",
        canonical_context=MetricDefinitionCaseContext(entities=["orders"], dimensions=["order_amount"]),
        expected_metric={
            "name": "total_revenue",
            "business_name": "Tổng doanh thu",
            "description": "Tổng doanh thu",
            "metric_type": "simple",
            "target_entity": "orders",
            "source_table": "orders",
            "aggregation": "sum",
            "field": "amount",
            "business_formula": "SUM(order_amount)",
            "sql_expression": "SUM(amount)",
            "allowed_dimensions": ["order_month"],
            "default_time_grain": "month",
            "reference_source": "mini",
            "status": "approved",
            "owner": "expert",
        },
        expected_preview_facts=["Tổng doanh thu"],
        tags=["mini", "simple"],
    )


def _negative_metric_case() -> MetricDefinitionCase:
    return MetricDefinitionCase(
        case_id="metric_002",
        request="Chỉ số không được hỗ trợ",
        canonical_context=MetricDefinitionCaseContext(entities=["orders"], dimensions=["order_amount"]),
        expected_error="UNSUPPORTED_REQUEST",
        tags=["mini", "negative"],
    )


def _query_case() -> QueryCase:
    return QueryCase(
        case_id="query_001",
        question="Tổng doanh thu theo tháng",
        difficulty="easy",
        expected=QueryCaseExpected(
            intent="aggregate",
            domain="mini",
            retrieval={"metrics": [], "entities": [], "dimensions": [], "relationships": []},
            canonical_query={
                "intent": "aggregate",
                "domain": "mini",
                "primary_entity": "orders",
                "metrics": ["total_revenue"],
                "dimensions": ["order_month"],
            },
            sql_by_dialect={
                "sqlite": "SELECT order_month, SUM(amount) AS total FROM orders GROUP BY order_month LIMIT 100"
            },
            result_ref="query_001",
        ),
        tags=["mini", "easy"],
    )


def _negative_query_case() -> QueryCase:
    return QueryCase(
        case_id="query_002",
        question="Tổng doanh thu theo chỉ số không tồn tại",
        difficulty="medium",
        expected_error="METRIC_NOT_FOUND",
        tags=["mini", "negative"],
    )


def _guardrail_case(sql: str = "SELECT * FROM orders", accepted: bool = True) -> GuardrailCase:
    expected = (
        GuardrailExpected(accepted=True, expected_limit=100, expected_timeout_seconds=15)
        if accepted
        else GuardrailExpected(accepted=False, error_code="NON_SELECT_STATEMENT")
    )
    return GuardrailCase(case_id="guard_001", sql=sql, dialect="sqlite", expected=expected, tags=["mini", "positive"])


@pytest.fixture
def mini_dataset(tmp_path: Path) -> DomainDataset:
    """Build one fully validated in-code domain dataset."""
    return DomainDataset(
        domain_dir=tmp_path / "mini",
        manifest=_manifest(),
        discovery_cases=[_discovery_case()],
        metric_cases=[_metric_case(), _negative_metric_case()],
        query_cases=[_query_case(), _negative_query_case()],
        guardrail_cases=[_guardrail_case()],
        raw_schemas={"mini_schema": _raw_schema()},  # type: ignore[arg-type]
        canonical_entities=_canonical_entities(),
        canonical_metrics=_canonical_metrics(),
        expected_query_results={"query_001": []},
    )


_EXECUTABLE_SQL = "SELECT order_month, SUM(amount) FROM orders GROUP BY order_month LIMIT 100"


def _executable_dataset(dataset: DomainDataset, tmp_path: Path) -> DomainDataset:
    """Point one dataset at isolated SQLite sources with seeded, runnable rows."""
    sources = tmp_path / "sources" / "sqlite"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "schema.sql").write_text(
        "CREATE TABLE orders (id INTEGER, amount REAL, order_month TEXT);", encoding="utf-8"
    )
    (sources / "seed_data.sql").write_text(
        "INSERT INTO orders VALUES (1, 10.0, '2026-01');\nINSERT INTO orders VALUES (2, 20.0, '2026-01');",
        encoding="utf-8",
    )
    positive = dataset.query_cases[0]
    assert positive.expected is not None
    expected = positive.expected.model_copy(update={"sql_by_dialect": {"sqlite": _EXECUTABLE_SQL}})
    queries = [positive.model_copy(update={"expected": expected}), *dataset.query_cases[1:]]
    negative_guard = _guardrail_case("DELETE FROM orders", accepted=False).model_copy(update={"case_id": "guard_002"})
    return dataset.model_copy(
        update={
            "domain_dir": tmp_path,
            "query_cases": queries,
            "guardrail_cases": [*dataset.guardrail_cases, negative_guard],
            "expected_query_results": {"query_001": [{"order_month": "2026-01", "SUM(amount)": 30.0}]},
        }
    )
