"""Tests for strict asynchronous Golden Dataset loading."""

from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.dataset.validator import DatasetValidationError

GOLDEN_ROOT = Path("eval/golden_dataset")
GROUND_TRUTH_METRICS = {
    "average_order_value",
    "cart_abandonment_rate",
    "conversion_rate",
    "customer_count",
    "gross_margin",
    "net_revenue",
    "order_count",
    "return_rate",
    "returning_customer_rate",
    "units_sold",
}
CANONICAL_ENTITIES = {
    "cart",
    "customer",
    "order",
    "order_item",
    "payment",
    "product",
    "session",
}


@pytest.mark.asyncio
async def test_load_ecommerce_domain_dataset() -> None:
    """Load every ecommerce artifact and verify baseline completeness."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    assert dataset.manifest.dataset_version == "2.0.1"
    assert dataset.manifest.contract_version == "2.0.0"
    assert dataset.manifest.ground_truth_metric_count == 10
    assert dataset.manifest.review_status == "pending"
    assert set(dataset.manifest.supported_dialects) == {"postgresql", "mysql", "sqlite"}
    assert len(dataset.discovery_cases) == 4
    assert len(dataset.metric_cases) == 12
    assert len(dataset.query_cases) == 32
    assert len(dataset.guardrail_cases) == 13
    assert len(dataset.expected_query_results) == 30
    assert len(dataset.raw_schemas) == 4
    assert set(dataset.canonical_entities) == CANONICAL_ENTITIES
    assert len(dataset.canonical_metrics) == 10
    assert "gross_margin" in dataset.canonical_metrics
    assert "payment_amount" not in dataset.canonical_metrics


@pytest.mark.asyncio
async def test_canonical_metrics_match_ground_truth_registry() -> None:
    """Keep the main registry limited to the agreed workbook metrics."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    assert set(dataset.canonical_metrics) == GROUND_TRUTH_METRICS
    for metric in dataset.canonical_metrics.values():
        assert metric.status == "draft"
        assert metric.owner == "Seller"
        assert metric.reference_source == "Shopify Analytics Fields"
        assert metric.ground_truth_source.endswith(f"#{metric.metric}")
        assert metric.allowed_dimensions


@pytest.mark.asyncio
async def test_vietnamese_case_text_has_no_encoding_replacement() -> None:
    """Reject question marks introduced inside words by a bad encoding pipe."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    assert all("?" not in case.request for case in dataset.metric_cases)
    for case in dataset.query_cases:
        assert "?" not in case.question.rstrip("?")
        assert "�" not in case.question


def test_domain_has_single_canonical_registry() -> None:
    """Do not retain parallel extension registries outside the benchmark."""
    canonical = GOLDEN_ROOT / "ecommerce" / "canonical"

    assert not (canonical / "metric_extensions").exists()
    assert not (canonical / "entity_extensions").exists()
    assert not (GOLDEN_ROOT / "ecommerce" / "sources" / "legacy").exists()


@pytest.mark.asyncio
async def test_loader_rejects_unsafe_domain_reference() -> None:
    """Prevent domain traversal outside the Golden Dataset root."""
    with pytest.raises(DatasetValidationError, match="Invalid domain identifier"):
        await load_domain_dataset(GOLDEN_ROOT, "../secrets")
