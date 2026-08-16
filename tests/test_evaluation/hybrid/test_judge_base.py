"""Tests for the judge runner: caching, retry, timeout, structured parsing."""

from types import SimpleNamespace
from unittest.mock import patch

from eval.evaluator.hybrid.judge.base import JudgeRequest, JudgeRunner, LangChainJudgeLLM
from eval.evaluator.hybrid.judge.cache import MemoryJudgeCache, judge_cache_key
from src.config import Settings

_GOOD = """```json
{"criteria": [{"name": "clarity", "score": 1.0}], "overall": 1.0, "summary": "fine"}
```"""


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def invoke(self, system: str, user: str) -> str:
        self.calls += 1
        return self.responses.pop(0)


def _request() -> JudgeRequest:
    return JudgeRequest(
        system_prompt="sys",
        user_prompt="usr",
        prompt_version="v1",
        rubric_version="1.0.0",
        model="fake",
        cache_key=judge_cache_key("s1", "h", "1.0.0", "v1", "fake"),
    )


async def test_parses_fenced_json_and_caches() -> None:
    llm = FakeLLM([_GOOD])
    cache = MemoryJudgeCache()
    runner = JudgeRunner(llm, cache)
    verdict = await runner.evaluate(_request())
    assert verdict is not None and verdict.overall == 1.0
    again = await runner.evaluate(_request())
    assert again == verdict
    assert llm.calls == 1  # second call served from cache


async def test_retries_then_succeeds() -> None:
    llm = FakeLLM(["not json at all", _GOOD])
    runner = JudgeRunner(llm, MemoryJudgeCache(), max_attempts=3)
    verdict = await runner.evaluate(_request())
    assert verdict is not None
    assert llm.calls == 2


async def test_returns_none_after_exhausted_retries() -> None:
    llm = FakeLLM(["nope", "nope", "nope"])
    runner = JudgeRunner(llm, MemoryJudgeCache(), max_attempts=3)
    assert await runner.evaluate(_request()) is None
    assert llm.calls == 3


async def test_schema_mismatch_is_retried_not_accepted() -> None:
    llm = FakeLLM(['{"criteria": [], "overall": 0.5}', _GOOD])
    runner = JudgeRunner(llm, MemoryJudgeCache(), max_attempts=2)
    verdict = await runner.evaluate(_request())
    assert verdict is not None and verdict.overall == 1.0


def test_langchain_judge_uses_isolated_model() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="agent-secret",
        model_name="agent-model",
        judge_llm_provider="groq",
        judge_api_key="judge-secret",
        judge_model_name="judge-model",
    )

    def _client(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(model_name=kwargs["model"])

    with (
        patch("src.services.llm.get_settings", return_value=settings),
        patch("src.services.llm.ChatOpenAI", side_effect=_client),
    ):
        judge = LangChainJudgeLLM()
    assert judge.model_name == "judge-model"


def test_langchain_judge_accepts_native_protocol_model_attribute() -> None:
    client = SimpleNamespace(model="native-judge-model")
    with patch("src.services.llm.get_llm", return_value=client):
        judge = LangChainJudgeLLM()
    assert judge.model_name == "native-judge-model"
