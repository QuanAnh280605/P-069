"""Pure join-path analysis for the deterministic semantic compiler.

Enumerates child->parent ``many_to_one`` join paths through governed, approved
relationships and resolves the single safe path, failing closed on ambiguity.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from src.models.db import CanonicalRelationshipModel
from src.models.review_mixin import REVIEW_STATUS_APPROVED
from src.services.semantic_compile_error import SemanticCompileError


@dataclass(frozen=True)
class JoinPathCandidate:
    """One equal-shortest child->parent many_to_one path between two entities."""

    relationship_ids: tuple[int, ...]
    entity_sequence: tuple[int, ...]


def is_traversable(relationship: CanonicalRelationshipModel) -> bool:
    """Return True only for governed, approved, child->parent many_to_one links.

    The authoritative compile-time safety gate requires three independent
    signals: the relationship is technically valid, has been human-approved via
    HITL review, and points in the safe child->parent direction. Legacy rows
    whose ``validation_status`` was never set (``None``) are treated as
    non-compilable rather than silently trusted.
    """
    return (
        relationship.validation_status == "valid"
        and relationship.review_status == REVIEW_STATUS_APPROVED
        and relationship.relationship_type in {"many_to_one", "many-to-one"}
    )


def _build_traversable_graph(
    relationships: list[CanonicalRelationshipModel],
) -> dict[int, list[CanonicalRelationshipModel]]:
    graph: dict[int, list[CanonicalRelationshipModel]] = {}
    for rel in relationships:
        if is_traversable(rel):
            graph.setdefault(rel.from_entity_id, []).append(rel)
    return graph


def _shortest_paths(
    graph: dict[int, list[CanonicalRelationshipModel]],
    start: int,
    target: int,
) -> list[list[CanonicalRelationshipModel]]:
    """Return every equal-shortest relationship path from start to target."""
    queue: deque[tuple[int, list[CanonicalRelationshipModel], set[int]]] = deque([(start, [], {start})])
    matches: list[list[CanonicalRelationshipModel]] = []
    shortest: int | None = None
    while queue:
        current, path, visited = queue.popleft()
        if current == target:
            shortest = len(path) if shortest is None else shortest
            if len(path) == shortest:
                matches.append(path)
            continue
        if shortest is not None and len(path) >= shortest:
            continue
        for relationship in graph.get(current, []):
            if relationship.to_entity_id not in visited:
                queue.append(
                    (
                        relationship.to_entity_id,
                        [*path, relationship],
                        {*visited, relationship.to_entity_id},
                    )
                )
    return matches


def _to_candidates(start: int, paths: list[list[CanonicalRelationshipModel]]) -> list[JoinPathCandidate]:
    """Convert raw relationship paths into deterministically ordered candidates."""
    candidates = [
        JoinPathCandidate(
            relationship_ids=tuple(rel.id for rel in path),
            entity_sequence=tuple([start, *(rel.to_entity_id for rel in path)]),
        )
        for path in paths
    ]
    candidates.sort(key=lambda candidate: candidate.relationship_ids)
    return candidates


def enumerate_join_paths(
    relationships: list[CanonicalRelationshipModel],
    start: int,
    target: int,
) -> list[JoinPathCandidate]:
    """Return every equal-shortest child->parent many_to_one path as candidates.

    Only governed, approved, technically-valid relationships are traversed. The
    result is ordered deterministically by relationship-id sequence so insertion
    order never changes the candidate set or its ordering.
    """
    graph = _build_traversable_graph(relationships)
    return _to_candidates(start, _shortest_paths(graph, start, target))


def _ambiguous_error(
    base_id: int,
    target_id: int,
    candidates: list[JoinPathCandidate],
) -> SemanticCompileError:
    """Build the fail-closed ambiguity error with candidate relationship sequences."""
    return SemanticCompileError(
        "AMBIGUOUS_JOIN_PATH",
        "Multiple safe join paths exist; a governed preferred path is required",
        {
            "base_entity_id": base_id,
            "target_entity_id": target_id,
            "candidate_paths": [list(candidate.relationship_ids) for candidate in candidates],
        },
    )


def join_path_options(
    relationships: list[CanonicalRelationshipModel],
    base_id: int,
) -> dict[int, list[dict[str, object]]]:
    """Return every safe join-path option keyed by reachable target entity id.

    Only governed, approved, technically-valid ``many_to_one`` relationships are
    traversed (same gate as :func:`enumerate_join_paths`). For each target entity
    reachable from ``base_id`` the result lists every equal-shortest candidate with
    its relationship-id sequence, full entity sequence, and the per-relationship
    business labels and descriptions so a UI can present governed choices.
    """
    rel_by_id = {rel.id: rel for rel in relationships}
    graph = _build_traversable_graph(relationships)
    options: dict[int, list[dict[str, object]]] = {}
    for target in sorted(_reachable_targets(graph, base_id)):
        candidates = enumerate_join_paths(relationships, base_id, target)
        if not candidates:
            continue
        options[target] = [_candidate_to_option(candidate, rel_by_id) for candidate in candidates]
    return options


def _reachable_targets(
    graph: dict[int, list[CanonicalRelationshipModel]],
    base_id: int,
) -> set[int]:
    """Return every entity reachable from ``base_id`` through traversable links."""
    reachable: set[int] = set()
    queue: deque[int] = deque([base_id])
    seen: set[int] = {base_id}
    while queue:
        current = queue.popleft()
        for rel in graph.get(current, []):
            if rel.to_entity_id not in seen:
                seen.add(rel.to_entity_id)
                reachable.add(rel.to_entity_id)
                queue.append(rel.to_entity_id)
    return reachable


def _candidate_to_option(
    candidate: JoinPathCandidate,
    rel_by_id: dict[int, CanonicalRelationshipModel],
) -> dict[str, object]:
    """Project one candidate path into the governed join-path option DTO."""
    rels = [rel_by_id[rel_id] for rel_id in candidate.relationship_ids]
    return {
        "relationship_ids": list(candidate.relationship_ids),
        "entity_ids": list(candidate.entity_sequence),
        "labels": [rel.business_name for rel in rels],
        "descriptions": [rel.description for rel in rels],
    }


def ambiguous_relationship_groups(
    relationships: list[CanonicalRelationshipModel],
) -> dict[int, list[dict[str, object]]]:
    """Return ambiguity info for relationships in the review queue.

    Considers every ``many_to_one`` relationship (review/validation status
    ignored) and maps relationship id -> list of equal-length join-path target
    groups, each with candidate relationship-id sequences to disambiguate.
    """
    graph: dict[int, list[CanonicalRelationshipModel]] = {}
    for rel in relationships:
        if rel.relationship_type in {"many_to_one", "many-to-one"}:
            graph.setdefault(rel.from_entity_id, []).append(rel)

    pairs: dict[tuple[int, int], list[CanonicalRelationshipModel]] = {}
    for rel in relationships:
        if rel.relationship_type in {"many_to_one", "many-to-one"}:
            pairs.setdefault((rel.from_entity_id, rel.to_entity_id), []).append(rel)

    result: dict[int, list[dict[str, object]]] = {}
    for (frm, to), rels in pairs.items():
        candidates = _to_candidates(frm, _shortest_paths(graph, frm, to))
        if len(candidates) > 1:
            group = {
                "target_entity_id": to,
                "candidate_relationship_ids": [list(c.relationship_ids) for c in candidates],
            }
            for rel in rels:
                result.setdefault(rel.id, []).append(group)
    return result


def _fanout_error(target_id: int) -> SemanticCompileError:
    """Build the one-to-many fanout error for a reverse-only dimension path."""
    return SemanticCompileError(
        "UNSAFE_FANOUT",
        "Dimension requires a one-to-many join",
        {"table_id": target_id},
    )


def _unreachable_error(target_id: int) -> SemanticCompileError:
    """Build the unreachable-dimension error when no safe path exists."""
    return SemanticCompileError(
        "UNREACHABLE_DIMENSION",
        "Dimension is not reachable through a safe path",
        {"table_id": target_id},
    )


def _invalid_preferred_error(
    base_id: int,
    target_id: int,
    preferred_path: tuple[int, ...],
    candidates: list[JoinPathCandidate],
) -> SemanticCompileError:
    """Build the fail-closed error for a stale or mismatched preferred path."""
    return SemanticCompileError(
        "INVALID_PREFERRED_JOIN_PATH",
        "Persisted preferred join path is stale or does not match a safe candidate",
        {
            "base_entity_id": base_id,
            "target_entity_id": target_id,
            "preferred_path": list(preferred_path),
            "candidate_paths": [list(candidate.relationship_ids) for candidate in candidates],
        },
    )


def _conflicting_join_path_error(
    base_id: int,
    target_id: int,
    entries: list[tuple[int, tuple[int, ...]]],
) -> SemanticCompileError:
    """Build the fail-closed error when selected metrics disagree on a join path.

    ``entries`` is a list of ``(metric_id, relationship_id_sequence)`` pairs for the
    same ``(base_entity_id, target_entity_id)``. The context exposes every offending
    metric id alongside its chosen sequence so the caller can surface both sides.
    """
    return SemanticCompileError(
        "CONFLICTING_JOIN_PATH",
        "Selected metrics specify different join paths for the same target entity",
        {
            "base_entity_id": base_id,
            "target_entity_id": target_id,
            "conflicts": [{"metric_id": metric_id, "relationship_ids": list(path)} for metric_id, path in entries],
        },
    )


def _select_preferred(
    candidates: list[JoinPathCandidate],
    preferred_path: tuple[int, ...] | None,
) -> JoinPathCandidate | None:
    """Return the candidate matching the governed preferred path, if any."""
    if preferred_path is None:
        return None
    for candidate in candidates:
        if candidate.relationship_ids == preferred_path:
            return candidate
    return None


def resolve_join_path(
    relationships: list[CanonicalRelationshipModel],
    base_id: int,
    target_id: int,
    preferred_path: tuple[int, ...] | None = None,
) -> JoinPathCandidate:
    """Resolve the single safe join path or fail closed.

    - one candidate -> return it
    - multiple candidates and no preferred path (or preferred not among them)
      -> raise ``AMBIGUOUS_JOIN_PATH`` with base/target entity ids and the
      candidate relationship-id sequences
    - no forward candidate but a reverse path exists -> raise ``UNSAFE_FANOUT``
    - no path at all -> raise ``UNREACHABLE_DIMENSION``
    """
    candidates = enumerate_join_paths(relationships, base_id, target_id)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        preferred = _select_preferred(candidates, preferred_path)
        if preferred is not None:
            return preferred
        raise _ambiguous_error(base_id, target_id, candidates)
    if enumerate_join_paths(relationships, target_id, base_id):
        raise _fanout_error(target_id)
    raise _unreachable_error(target_id)
