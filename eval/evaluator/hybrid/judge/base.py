"""Judge LLM adapter and bounded-retry runner (spec §8.2)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from eval.evaluator.hybrid.judge.cache import JudgeCache
from eval.evaluator.hybrid.judge.output import JudgeVerdict

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class JudgeLLM(Protocol):
    """Invoke one judge completion with system and user prompts."""

    async def invoke(self, system: str, user: str) -> str: ...


class LangChainJudgeLLM:
    """Adapt the product LLM client for judge use (get_llm, temperature 0.0)."""

    def __init__(self) -> None:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.services.llm import get_llm

        self._llm = get_llm(role="judge")
        self._message_types = (SystemMessage, HumanMessage)
        self.model_name = str(getattr(self._llm, "model_name", getattr(self._llm, "model", "configured-model")))

    async def invoke(self, system: str, user: str) -> str:
        system_type, human_type = self._message_types
        message = await self._llm.ainvoke([system_type(content=system), human_type(content=user)])
        return str(message.content)


@dataclass(frozen=True)
class JudgeRequest:
    """Carry one fully rendered judge call and its provenance."""

    system_prompt: str
    user_prompt: str
    prompt_version: str
    rubric_version: str
    model: str
    cache_key: str


class JudgeRunner:
    """Run judge calls with caching, timeout, and bounded retries."""

    def __init__(
        self,
        llm: JudgeLLM,
        cache: JudgeCache,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
    ) -> None:
        self.llm = llm
        self.cache = cache
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    async def evaluate(self, request: JudgeRequest) -> JudgeVerdict | None:
        """Return the cached or freshly computed verdict, or None on exhaustion."""
        cached = await self.cache.get(request.cache_key)
        if cached is not None:
            return cached
        for _ in range(self.max_attempts):
            verdict = await self._attempt(request)
            if verdict is not None:
                await self.cache.set(request.cache_key, verdict)
                return verdict
        return None

    async def _attempt(self, request: JudgeRequest) -> JudgeVerdict | None:
        try:
            raw = await asyncio.wait_for(
                self.llm.invoke(request.system_prompt, request.user_prompt), self.timeout_seconds
            )
            return JudgeVerdict.model_validate_json(extract_json(raw))
        except (TimeoutError, ValidationError, ValueError):
            return None


def extract_json(raw: str) -> str:
    """Strip markdown code fences from a judge completion."""
    match = _FENCE.search(raw)
    return match.group(1) if match else raw.strip()
