"""Content-hash keyed judge caches (spec §8.2: cache by sample, content, versions, model)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Protocol

from eval.evaluator.hybrid.judge.output import JudgeVerdict


def content_hash(payload: str) -> str:
    """Hash one candidate payload for immutable replay and caching."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def judge_cache_key(
    sample_id: str,
    response_hash: str,
    rubric_version: str,
    prompt_version: str,
    model: str,
) -> str:
    """Build the deterministic cache key for one judge call."""
    joined = "\n".join((sample_id, response_hash, rubric_version, prompt_version, model))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class JudgeCache(Protocol):
    """Store and retrieve verdicts by deterministic cache key."""

    async def get(self, key: str) -> JudgeVerdict | None: ...

    async def set(self, key: str, verdict: JudgeVerdict) -> None: ...


class MemoryJudgeCache:
    """In-memory cache for one process."""

    def __init__(self) -> None:
        self._entries: dict[str, JudgeVerdict] = {}

    async def get(self, key: str) -> JudgeVerdict | None:
        return self._entries.get(key)

    async def set(self, key: str, verdict: JudgeVerdict) -> None:
        self._entries[key] = verdict


class FileJudgeCache:
    """JSON-file-per-key cache persisted under one root directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def get(self, key: str) -> JudgeVerdict | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        raw = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return JudgeVerdict.model_validate(json.loads(raw))

    async def set(self, key: str, verdict: JudgeVerdict) -> None:
        path = self.root / f"{key}.json"
        payload = verdict.model_dump_json(indent=2)
        await asyncio.to_thread(path.write_text, payload, encoding="utf-8")
