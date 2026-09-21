"""Pure unit tests for join-path enumeration and fail-closed resolution."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import CanonicalRelationshipModel, SemanticColumnModel
from src.models.review_mixin import REVIEW_STATUS_APPROVED, REVIEW_STATUS_PENDING
from src.services.join_path_service import (
    JoinPathCandidate,
    enumerate_join_paths,
    is_traversable,
    join_path_options,
    resolve_join_path,
)
from src.services.semantic_compile_error import SemanticCompileError


def _rel(
    rel_id: int,
    from_id: int,
    to_id: int,
    validation_status: str = "valid",
    review_status: str = REVIEW_STATUS_APPROVED,
    rel_type: str = "many_to_one",
    business_name: str = "",
    description: str | None = None,
) -> CanonicalRelationshipModel:
    return CanonicalRelationshipModel(
        id=rel_id,
        connection_id=1,
        from_entity_id=from_id,
        to_entity_id=to_id,
        relationship_type=rel_type,
        join_condition="x",
        column_pairs=[],
        validation_status=validation_status,
        review_status=review_status,
        business_name=business_name,
        description=description,
    )


def test_is_traversable_requires_valid_approved_many_to_one() -> None:
    assert is_traversable(_rel(1, 1, 2)) is True
    assert is_traversable(_rel(1, 1, 2, validation_status="invalid")) is False
    assert is_traversable(_rel(1, 1, 2, review_status=REVIEW_STATUS_PENDING)) is False
    assert is_traversable(_rel(1, 1, 2, rel_type="one_to_many")) is False


def test_is_traversable_rejects_legacy_none_validation() -> None:
    rel = _rel(1, 1, 2)
    rel.validation_status = None  # type: ignore[assignment]
    assert is_traversable(rel) is False


def test_zero_paths_unreachable() -> None:
    rels = [_rel(1, 1, 2)]
    with pytest.raises(SemanticCompileError) as error:
        resolve_join_path(rels, base_id=3, target_id=4)
    assert error.value.code == "UNREACHABLE_DIMENSION"


def test_single_path_returns_candidate() -> None:
    rels = [_rel(1, 1, 2)]
    candidate = resolve_join_path(rels, base_id=1, target_id=2)
    assert candidate == JoinPathCandidate(relationship_ids=(1,), entity_sequence=(1, 2))


def test_single_multi_hop_path_returns_full_sequence() -> None:
    rels = [_rel(1, 1, 2), _rel(2, 2, 3)]
    candidate = resolve_join_path(rels, base_id=1, target_id=3)
    assert candidate.relationship_ids == (1, 2)
    assert candidate.entity_sequence == (1, 2, 3)


def test_multiple_equal_shortest_paths_are_ambiguous() -> None:
    # orders(1) -> order_lines(3) -> products(2)  and  orders(1) -> snapshots(4) -> products(2)
    rels = [
        _rel(10, 1, 3),
        _rel(11, 3, 2),
        _rel(12, 1, 4),
        _rel(13, 4, 2),
    ]
    candidates = enumerate_join_paths(rels, 1, 2)
    assert len(candidates) == 2

    with pytest.raises(SemanticCompileError) as error:
        resolve_join_path(rels, base_id=1, target_id=2)
    assert error.value.code == "AMBIGUOUS_JOIN_PATH"
    context = error.value.context
    assert context["base_entity_id"] == 1
    assert context["target_entity_id"] == 2
    assert {tuple(p) for p in context["candidate_paths"]} == {(10, 11), (12, 13)}


def test_preferred_path_disambiguates_multiple_candidates() -> None:
    rels = [
        _rel(10, 1, 3),
        _rel(11, 3, 2),
        _rel(12, 1, 4),
        _rel(13, 4, 2),
    ]
    candidate = resolve_join_path(rels, base_id=1, target_id=2, preferred_path=(12, 13))
    assert candidate.relationship_ids == (12, 13)


def test_preferred_path_not_in_candidates_still_ambiguous() -> None:
    rels = [
        _rel(10, 1, 3),
        _rel(11, 3, 2),
        _rel(12, 1, 4),
        _rel(13, 4, 2),
    ]
    with pytest.raises(SemanticCompileError) as error:
        resolve_join_path(rels, base_id=1, target_id=2, preferred_path=(99,))
    assert error.value.code == "AMBIGUOUS_JOIN_PATH"


def test_invalid_relationships_excluded_from_enumeration() -> None:
    rels = [
        _rel(1, 1, 2, validation_status="invalid"),
        _rel(2, 1, 2, review_status=REVIEW_STATUS_PENDING),
        _rel(3, 1, 2, rel_type="one_to_many"),
    ]
    assert enumerate_join_paths(rels, 1, 2) == []
    with pytest.raises(SemanticCompileError) as error:
        resolve_join_path(rels, base_id=1, target_id=2)
    assert error.value.code == "UNREACHABLE_DIMENSION"


def test_fanout_reverse_path_raises_unsafe_fanout() -> None:
    # customers(2) is the base; orders(1) is the dimension; only orders->customers exists.
    rels = [_rel(1, 1, 2)]
    with pytest.raises(SemanticCompileError) as error:
        resolve_join_path(rels, base_id=2, target_id=1)
    assert error.value.code == "UNSAFE_FANOUT"


def test_cycle_does_not_loop_and_returns_shortest() -> None:
    # A(1)->B(2), B(2)->A(1) cycle plus A(1)->C(3); target C reachable once.
    rels = [_rel(1, 1, 2), _rel(2, 2, 1), _rel(3, 1, 3)]
    candidates = enumerate_join_paths(rels, 1, 3)
    assert candidates == [JoinPathCandidate(relationship_ids=(3,), entity_sequence=(1, 3))]


def test_insertion_order_does_not_change_candidates() -> None:
    rels_forward = [
        _rel(10, 1, 3),
        _rel(11, 3, 2),
        _rel(12, 1, 4),
        _rel(13, 4, 2),
    ]
    rels_reversed = list(reversed(rels_forward))
    assert enumerate_join_paths(rels_forward, 1, 2) == enumerate_join_paths(rels_reversed, 1, 2)

    with pytest.raises(SemanticCompileError) as fwd:
        resolve_join_path(rels_forward, base_id=1, target_id=2)
    with pytest.raises(SemanticCompileError) as rev:
        resolve_join_path(rels_reversed, base_id=1, target_id=2)
    assert fwd.value.code == rev.value.code == "AMBIGUOUS_JOIN_PATH"
    assert fwd.value.context["candidate_paths"] == rev.value.context["candidate_paths"]


def test_join_path_options_lists_safe_candidates() -> None:
    rels = [
        _rel(10, 1, 3, business_name="Order line", description="order to line"),
        _rel(11, 3, 2, business_name="Product", description="line to product"),
        _rel(12, 1, 4, business_name="Snapshot", description="order to snapshot"),
        _rel(13, 4, 2, business_name="Product", description="snapshot to product"),
    ]
    options = join_path_options(rels, base_id=1)
    # products(2) reachable via two equal-shortest paths; order_lines(3) and snapshots(4) via one.
    assert set(options.keys()) == {2, 3, 4}
    product_options = options[2]
    assert len(product_options) == 2
    rel_ids = {tuple(opt["relationship_ids"]) for opt in product_options}
    assert rel_ids == {(10, 11), (12, 13)}
    for opt in product_options:
        assert opt["entity_ids"][0] == 1
        assert opt["entity_ids"][-1] == 2
        assert all(isinstance(label, str) and label for label in opt["labels"])
        assert all(d is None or isinstance(d, str) for d in opt["descriptions"])


def test_join_path_options_excludes_non_traversable_relationships() -> None:
    rels = [
        _rel(1, 1, 2, validation_status="invalid"),
        _rel(2, 1, 2, review_status=REVIEW_STATUS_PENDING),
        _rel(3, 1, 2, rel_type="one_to_many"),
    ]
    assert join_path_options(rels, base_id=1) == {}


def test_join_path_options_omits_base_entity() -> None:
    rels = [_rel(1, 1, 2)]
    options = join_path_options(rels, base_id=1)
    assert 1 not in options
    assert 2 in options


async def test_validate_preferred_join_paths_rejects_stale_path(async_session: AsyncSession) -> None:
    from src.models.db import SemanticTableModel
    from src.models.metric_definition import MetricDefinition
    from src.services.metric_definitions import validate_metric_definition

    base = SemanticTableModel(db_id=1, table_name="orders", business_name="", description="", primary_key_column="id")
    target = SemanticTableModel(
        db_id=1, table_name="products", business_name="", description="", primary_key_column="id"
    )
    async_session.add_all([base, target])
    await async_session.flush()
    async_session.add(
        CanonicalRelationshipModel(
            id=101,
            connection_id=1,
            from_entity_id=base.id,
            to_entity_id=target.id,
            relationship_type="many_to_one",
            join_condition="orders.product_id = products.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[],
        )
    )
    await async_session.commit()

    definition = MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Revenue",
                "formula": {"function": "SUM", "expression": "amount"},
                "base_entity": "orders",
                "preferred_join_paths": {target.id: [999]},
            }
        }
    )
    with pytest.raises(ValueError):
        await validate_metric_definition(async_session, 1, definition)


async def test_validate_preferred_join_paths_accepts_matching_path(async_session: AsyncSession) -> None:
    from src.models.db import SemanticTableModel
    from src.models.metric_definition import MetricDefinition
    from src.services.metric_definitions import validate_metric_definition

    base = SemanticTableModel(db_id=1, table_name="orders", business_name="", description="", primary_key_column="id")
    target = SemanticTableModel(
        db_id=1, table_name="products", business_name="", description="", primary_key_column="id"
    )
    async_session.add_all([base, target])
    await async_session.flush()
    async_session.add(
        SemanticColumnModel(table_id=base.id, column_name="amount", data_type="NUMERIC", business_name="amount")
    )
    async_session.add(
        CanonicalRelationshipModel(
            id=101,
            connection_id=1,
            from_entity_id=base.id,
            to_entity_id=target.id,
            relationship_type="many_to_one",
            join_condition="orders.product_id = products.id",
            review_status=REVIEW_STATUS_APPROVED,
            column_pairs=[],
        )
    )
    await async_session.commit()

    definition = MetricDefinition.model_validate(
        {
            "metric": {
                "name": "Revenue",
                "formula": {"function": "SUM", "expression": "amount"},
                "base_entity": "orders",
                "preferred_join_paths": {target.id: [101]},
            }
        }
    )
    table = await validate_metric_definition(async_session, 1, definition)
    assert table.id == base.id
