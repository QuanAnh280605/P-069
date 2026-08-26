"""Tests for strict asynchronous Golden Dataset loading."""

from pathlib import Path

import pytest

from eval.dataset.loader import load_domain_dataset
from eval.dataset.validator import DatasetValidationError

GOLDEN_ROOT = Path("eval/golden_dataset")
GROUND_TRUTH_METRICS = {
    "add_to_cart_rate",
    "average_delivery_lead_time_hours",
    "average_order_value",
    "average_session_duration",
    "cart_abandonment_rate",
    "checkout_abandonment_rate",
    "conversion_rate",
    "customer_count",
    "discount_rate",
    "gross_margin",
    "loyalty_order_penetration",
    "low_stock_sku_count",
    "net_revenue",
    "order_cancellation_rate",
    "order_count",
    "returned_order_rate",
    "returning_customer_rate",
    "units_per_transaction",
    "units_sold",
}
CANONICAL_ENTITIES = {
    "address",
    "cart",
    "city",
    "customer",
    "item",
    "order",
    "order_item",
    "payment",
    "product",
    "session",
}
REFERENCE_SOURCES = {"Shopify Analytics Fields", "Ecommerce Metric Dictionary (Expanded)"}
# Golden renames whose workbook anchor keeps the original row name.
WORKBOOK_ANCHOR_RENAMES = {"returned_order_rate": "return_rate"}


@pytest.mark.asyncio
async def test_load_ecommerce_domain_dataset() -> None:
    """Load every ecommerce artifact and verify baseline completeness."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    assert dataset.manifest.dataset_version == "3.0.0"
    assert dataset.manifest.contract_version == "2.1.0"
    assert dataset.manifest.ground_truth_metric_count == 19
    assert dataset.manifest.review_status == "pending"
    assert set(dataset.manifest.supported_dialects) == {"postgresql", "mysql", "sqlite"}
    assert len(dataset.discovery_cases) == 4
    assert len(dataset.metric_cases) == 21
    assert len(dataset.query_cases) == 39
    assert len(dataset.guardrail_cases) == 16
    assert len(dataset.expected_query_results) == 34
    assert len(dataset.raw_schemas) == 4
    assert set(dataset.canonical_entities) == CANONICAL_ENTITIES
    assert len(dataset.canonical_metrics) == 19
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
        assert metric.reference_source in REFERENCE_SOURCES
        anchor = WORKBOOK_ANCHOR_RENAMES.get(metric.metric, metric.metric)
        assert metric.ground_truth_source.endswith(f"#{anchor}")
        assert metric.allowed_dimensions


@pytest.mark.asyncio
async def test_vietnamese_case_text_has_no_encoding_replacement() -> None:
    """Reject question marks introduced inside words by a bad encoding pipe."""
    dataset = await load_domain_dataset(GOLDEN_ROOT, "ecommerce")

    # A sentence-final question mark is legitimate; mid-text "?" flags mojibake.
    assert all("?" not in case.request.rstrip("?") for case in dataset.metric_cases)
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
