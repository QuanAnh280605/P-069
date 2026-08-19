"""Tests for hybrid enrichment metrics."""

from eval.evaluator.hybrid.catalog import metrics_for_task
from eval.evaluator.hybrid.engine import EvaluationContext
from eval.evaluator.hybrid.metrics.enrichment import build_enrichment_metrics
from eval.evaluator.hybrid.samples import build_samples
from eval.evaluator.schemas import (
    CandidateDimension,
    CandidateEnrichmentOutput,
    CandidateEntity,
    CandidateRelationship,
    EvaluationConfig,
)


def _enrichment_sample(mini_dataset, entities):
    samples = build_samples(mini_dataset, {}, {"disc_001": CandidateEnrichmentOutput(entities=entities)}, {}, {}, {})
    return next(s for s in samples if s.task == "enrichment")


async def test_perfect_candidate(mini_dataset) -> None:
    metrics = build_enrichment_metrics(metrics_for_task("enrichment"))
    entities = (
        CandidateEntity(
            entity="orders",
            business_name="Đơn hàng",
            dimensions=(CandidateDimension(name="order_amount", business_name="Giá trị đơn hàng"),),
            relationships=(
                CandidateRelationship(
                    source_entity="orders",
                    source_field="customer_id",
                    target_entity="customers",
                    target_field="id",
                    relation_type="BELONGS_TO",
                ),
            ),
        ),
    )
    sample = _enrichment_sample(mini_dataset, entities)
    results = [await m.score(sample, EvaluationContext(EvaluationConfig())) for m in metrics.values()]
    assert all(r.status == "passed" for r in results)


async def test_missing_entity_fails_entity_f1(mini_dataset) -> None:
    metrics = build_enrichment_metrics(metrics_for_task("enrichment"))
    sample = _enrichment_sample(mini_dataset, ())
    result = await metrics["entity_f1"].score(sample, EvaluationContext(EvaluationConfig()))
    assert result.status == "failed" and result.score == 0.0


async def test_wrong_business_name_lowers_similarity(mini_dataset) -> None:
    metrics = build_enrichment_metrics(metrics_for_task("enrichment"))
    entities = (
        CandidateEntity(
            entity="orders",
            business_name="Hoá đơn bán",  # same meaning, different wording
            dimensions=(CandidateDimension(name="order_amount", business_name="Giá trị đơn hàng"),),
        ),
    )
    sample = _enrichment_sample(mini_dataset, entities)
    result = await metrics["business_name_similarity"].score(sample, EvaluationContext(EvaluationConfig()))
    assert 0.0 <= result.score < 1.0
