"""Semaphore-safe LLM caller with retry for the enrichment pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any

from src.services.enrichment_config import DEFAULT_CONFIG, EnrichmentConfig
from src.services.llm import get_llm

logger = logging.getLogger(__name__)


def parse_llm_json(content: str) -> Any:
    """Extract JSON from LLM text using 4 fallback strategies."""
    cleaned = content.strip()

    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        code_content = match.group(1).strip()
        try:
            return json.loads(code_content)
        except json.JSONDecodeError:
            cleaned = code_content

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for start_char in ("{", "["):
        start_idx = cleaned.find(start_char)
        if start_idx != -1:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(cleaned[start_idx:])
                return obj
            except json.JSONDecodeError:
                pass

    start_obj, end_obj = cleaned.find("{"), cleaned.rfind("}")
    if start_obj != -1 and end_obj > start_obj:
        try:
            return json.loads(cleaned[start_obj : end_obj + 1])
        except json.JSONDecodeError:
            pass

    start_arr, end_arr = cleaned.find("["), cleaned.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        return json.loads(cleaned[start_arr : end_arr + 1])

    raise ValueError(f"No valid JSON found in LLM output: {content[:150]}")


async def execute_llm_request(
    prompt: str,
    sem: asyncio.Semaphore,
    timeout_sec: float = 30.0,
) -> str:
    """Call LLM inside semaphore with timeout. Returns response content."""
    llm = get_llm()
    async with sem:
        response = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=timeout_sec,
        )
    return response.content


async def enrich_cluster_with_retry(
    cluster_prompt_builder: Callable[..., str],
    cluster: list[dict],
    global_glossary: dict,
    dialect: str,
    sem: asyncio.Semaphore,
    config: EnrichmentConfig | None = None,
) -> dict:
    """Enrich a table cluster via LLM with retry and fallback."""
    if config is None:
        config = DEFAULT_CONFIG

    table_names = [t["table_name"] for t in cluster]
    total_tables = len(cluster)

    for attempt in range(config.retry_max_attempts + 1):
        is_retry = attempt > 0
        try:
            prompt = cluster_prompt_builder(
                cluster,
                global_glossary,
                dialect,
                is_retry=is_retry,
            )
            raw = await execute_llm_request(prompt, sem, config.llm_call_timeout_sec)
            parsed = parse_llm_json(raw)

            matched = parsed.get("matched_tables", [])
            ratio = len(matched) / total_tables if total_tables else 0.0

            if ratio >= config.llm_match_threshold:
                logger.info(
                    "Cluster enriched: %d/%d tables matched (attempt %d)",
                    len(matched),
                    total_tables,
                    attempt,
                )
                return parsed

            logger.info(
                "Cluster below threshold: %d/%d < %.2f (attempt %d)",
                len(matched),
                total_tables,
                config.llm_match_threshold,
                attempt,
            )
        except Exception as exc:
            logger.warning(
                "LLM call failed (attempt %d/%d): %s",
                attempt + 1,
                config.retry_max_attempts + 1,
                exc,
            )

        if attempt < config.retry_max_attempts:
            backoff = config.retry_backoff_base_sec * (attempt + 1)
            await asyncio.sleep(backoff)

    logger.warning(
        "Cluster enrichment exhausted after %d attempts, using fallback",
        config.retry_max_attempts + 1,
    )
    return {
        "source": "fallback",
        "tables": table_names,
        "matched_tables": [],
        "metrics": [],
    }
