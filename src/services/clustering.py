"""Hub-Detached Domain Graph Partitioning for Two-Pass Semantic Enrichment."""

from __future__ import annotations

import logging
from collections import deque

from src.models.raw_schema import TableMetadata
from src.services.enrichment_config import DEFAULT_CONFIG, EnrichmentConfig

logger = logging.getLogger(__name__)


def table_key(t: TableMetadata) -> str:
    """Return 'schema.table' if schema_name exists, else 'table_name'."""
    schema = t.get("schema_name")
    if schema:
        return f"{schema}.{t['table_name']}"
    return t["table_name"]


def _compute_in_degrees(tables: list[TableMetadata]) -> dict[str, int]:
    """Count how many OTHER tables FK point TO each table.

    - Exclude self-referencing FK (fk.referred_table == table.table_name)
    - Deduplicate composite FK: each source table counts ONCE per destination
    - Guard FK orphan: skip + log warning if referred_table not in table_map
    """
    table_map: dict[str, str] = {t["table_name"]: table_key(t) for t in tables}
    in_degrees: dict[str, int] = {t["table_name"]: 0 for t in tables}

    for t in tables:
        src_name = t["table_name"]
        seen: set[str] = set()
        for fk in t.get("foreign_keys", []):
            ref_table = fk["referred_table"]
            if ref_table == src_name:
                continue
            if ref_table not in table_map:
                logger.warning(
                    "FK orphan: %s.%s references missing table %s",
                    src_name,
                    fk.get("constrained_columns"),
                    ref_table,
                )
                continue
            if ref_table not in seen:
                seen.add(ref_table)
                in_degrees[ref_table] += 1

    return in_degrees


def _identify_hub_tables(tables: list[TableMetadata], config: EnrichmentConfig = DEFAULT_CONFIG) -> set[str]:
    """Return set of table_names with in-degree >= config.hub_in_degree_threshold."""
    in_degrees = _compute_in_degrees(tables)
    return {name for name, deg in in_degrees.items() if deg >= config.hub_in_degree_threshold}


def _build_hub_detached_graph(tables: list[TableMetadata], hub_names: set[str]) -> dict[str, set[str]]:
    """Build UNDIRECTED graph with edges TO hub tables removed.

    Any edge touching a hub is removed. Guard FK orphan.
    """
    table_map: dict[str, str] = {t["table_name"]: table_key(t) for t in tables}
    graph: dict[str, set[str]] = {}

    for t in tables:
        src = t["table_name"]
        for fk in t.get("foreign_keys", []):
            ref = fk["referred_table"]
            if ref == src:
                continue
            if ref not in table_map:
                continue
            if src in hub_names or ref in hub_names:
                continue
            graph.setdefault(src, set()).add(ref)
            graph.setdefault(ref, set()).add(src)

    return graph


def _find_connected_components(graph: dict[str, set[str]], all_names: set[str]) -> list[set[str]]:
    """BFS to find connected components. Isolated nodes become singleton sets."""
    visited: set[str] = set()
    components: list[set[str]] = []

    for node in all_names:
        if node in visited:
            continue
        component: set[str] = set()
        queue = deque([node])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    return components


def _split_component_by_budget(
    component: set[str],
    table_map: dict[str, TableMetadata],
    config: EnrichmentConfig = DEFAULT_CONFIG,
) -> list[list[str]]:
    """Split a component into sub-clusters respecting column budget.

    BFS from anchor node (most FK connections, alphabetical tie-break).
    Accumulate tables in BFS order, each sub-cluster <= max_cols_per_cluster
    and <= max_tables_per_cluster. Single table exceeding max_cols → ultra-wide.
    """
    if not component:
        return []

    names = sorted(component)
    if len(names) == 1:
        t = table_map[names[0]]
        cols = len(t.get("columns", []))
        if cols > config.ultra_wide_threshold:
            return [[names[0]]]
        return [names]

    local: dict[str, set[str]] = {}
    for n in names:
        neighbors = set()
        for nb in _get_neighbors(n, table_map):
            if nb in component:
                neighbors.add(nb)
        local[n] = neighbors

    anchor = max(names, key=lambda n: (len(local[n]), n))

    visited: set[str] = set()
    queue = deque([anchor])
    bfs_order: list[str] = []
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        bfs_order.append(current)
        for nb in sorted(local.get(current, set())):
            if nb not in visited:
                queue.append(nb)

    result: list[list[str]] = []
    current_cluster: list[str] = []
    current_cols = 0

    for name in bfs_order:
        t = table_map[name]
        cols = len(t.get("columns", []))

        if not current_cluster:
            if cols > config.ultra_wide_threshold:
                result.append([name])
                continue
            current_cluster = [name]
            current_cols = cols
            continue

        if (
            current_cols + cols <= config.max_cols_per_cluster
            and len(current_cluster) + 1 <= config.max_tables_per_cluster
        ):
            current_cluster.append(name)
            current_cols += cols
        else:
            result.append(current_cluster)
            if cols > config.ultra_wide_threshold:
                result.append([name])
                current_cluster = []
                current_cols = 0
            else:
                current_cluster = [name]
                current_cols = cols

    if current_cluster:
        result.append(current_cluster)

    return result


def _get_neighbors(table_name: str, table_map: dict[str, TableMetadata]) -> set[str]:
    """Get all FK neighbors (undirected) for a table."""
    t = table_map[table_name]
    neighbors: set[str] = set()
    for fk in t.get("foreign_keys", []):
        ref = fk["referred_table"]
        if ref != table_name and ref in table_map:
            neighbors.add(ref)
    # Also check if other tables reference this one
    for other_name, other_t in table_map.items():
        if other_name == table_name:
            continue
        for fk in other_t.get("foreign_keys", []):
            if fk["referred_table"] == table_name:
                neighbors.add(other_name)
    return neighbors


def _classify_and_merge(
    tables: list[TableMetadata],
    raw_components: list[set[str]],
    hub_names: set[str],
    table_map: dict[str, TableMetadata],
    config: EnrichmentConfig = DEFAULT_CONFIG,
) -> list[list[TableMetadata]]:
    """Classify components and build final cluster list.

    Step A: Hub singletons, Domain components, Lookup singletons
    Step B: Hub Entity Clusters (hub + satellite tables)
    Returns: Domain clusters, Hub Entity clusters, Lookup clusters
    """
    hub_singletons: list[set[str]] = []
    domain_components: list[set[str]] = []

    for comp in raw_components:
        if len(comp) == 1 and next(iter(comp)) in hub_names:
            hub_singletons.append(comp)
        else:
            domain_components.append(comp)

    all_non_hub: set[str] = set()
    for comp in domain_components:
        all_non_hub.update(comp)

    assigned_satellites: set[str] = set()
    hub_entity_clusters: list[list[TableMetadata]] = []

    for hub_comp in hub_singletons:
        hub_name = next(iter(hub_comp))
        satellite_names: list[str] = []

        for t_name in all_non_hub:
            if t_name in assigned_satellites:
                continue
            t = table_map[t_name]
            outbound = [
                fk
                for fk in t.get("foreign_keys", [])
                if fk["referred_table"] != t_name and fk["referred_table"] in table_map
            ]
            if not outbound:
                continue
            all_to_hub = all(fk["referred_table"] in hub_names for fk in outbound)
            if not all_to_hub:
                continue
            # Satellite must reference THIS hub specifically
            refs_this_hub = any(fk["referred_table"] == hub_name for fk in outbound)
            if refs_this_hub:
                satellite_names.append(t_name)

        assigned_satellites.update(satellite_names)
        hub_entity = [hub_name] + sorted(satellite_names)
        sub_clusters = _split_component_by_budget(set(hub_entity), table_map, config)
        for sub in sub_clusters:
            hub_entity_clusters.append([table_map[n] for n in sub])

    remaining_domain: list[set[str]] = []
    for comp in domain_components:
        filtered = comp - assigned_satellites
        if filtered:
            remaining_domain.append(filtered)

    lookup_names = {
        t["table_name"]
        for t in tables
        if t["table_name"] not in hub_names
        and t["table_name"] not in assigned_satellites
        and not any(t["table_name"] in rc for rc in remaining_domain)
    }

    domain_clusters: list[list[TableMetadata]] = []
    for comp in remaining_domain:
        sub_clusters = _split_component_by_budget(comp, table_map, config)
        for sub in sub_clusters:
            domain_clusters.append([table_map[n] for n in sub])

    lookup_clusters: list[list[TableMetadata]] = []
    for name in sorted(lookup_names):
        lookup_clusters.append([table_map[name]])

    return domain_clusters + hub_entity_clusters + lookup_clusters


def cluster_tables(tables: list[TableMetadata], config: EnrichmentConfig | None = None) -> list[list[TableMetadata]]:
    """Cluster tables using Hub-Detached Domain Graph Partitioning.

    Returns list of clusters, each cluster is list of TableMetadata.
    Order: Domain clusters, Hub Entity clusters, Lookup clusters.
    """
    if not tables:
        return []

    if config is None:
        config = DEFAULT_CONFIG

    table_map: dict[str, TableMetadata] = {t["table_name"]: t for t in tables}

    hub_names = _identify_hub_tables(tables, config)
    graph = _build_hub_detached_graph(tables, hub_names)
    all_names = set(table_map.keys())
    raw_components = _find_connected_components(graph, all_names)

    return _classify_and_merge(tables, raw_components, hub_names, table_map, config)
