"""Centralized configuration for Two-Pass Semantic Enrichment pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnrichmentConfig:
    """Immutable configuration for enrichment pipeline."""

    hub_in_degree_threshold: int = 3
    max_cols_per_cluster: int = 45
    max_tables_per_cluster: int = 6
    max_concurrency: int = 3
    pass1_batch_size: int = 40
    pass1_single_prompt_threshold: int = 60
    ultra_wide_threshold: int = 40
    ultra_wide_chunk_size: int = 30
    retry_max_attempts: int = 2
    retry_backoff_base_sec: float = 1.0
    llm_match_threshold: float = 0.7
    llm_call_timeout_sec: float = 30.0


DEFAULT_CONFIG = EnrichmentConfig()
