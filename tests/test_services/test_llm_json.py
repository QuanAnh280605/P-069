"""Tests for the shared LLM JSON extraction helpers and the corrective retry."""

import json
from typing import Any

import pytest

from src.services.llm_json import (
    JSON_RETRY_INSTRUCTION,
    ainvoke_json,
    extract_json,
    response_text,
    strip_code_fence,
)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """Records every prompt and returns the queued replies in order."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.prompts: list[Any] = []

    async def ainvoke(self, prompt: Any) -> _FakeResponse:
        self.prompts.append(prompt)
        return _FakeResponse(self._replies[min(len(self.prompts) - 1, len(self._replies) - 1)])


# --- pure parsing -----------------------------------------------------------


def test_strip_code_fence_removes_json_fence() -> None:
    assert strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fence_keeps_plain_text() -> None:
    assert strip_code_fence('  {"a": 1}  ') == '{"a": 1}'


def test_extract_json_parses_fenced_object() -> None:
    assert extract_json('```json\n{"tables": []}\n```') == {"tables": []}


def test_extract_json_ignores_surrounding_prose() -> None:
    raw = 'Đây là kết quả:\n{"name": "Doanh thu"}\nHy vọng giúp được bạn.'
    assert extract_json(raw) == {"name": "Doanh thu"}


def test_extract_json_supports_array_payload() -> None:
    assert extract_json('Kết quả: [{"id": 1}, {"id": 2}]') == [{"id": 1}, {"id": 2}]


def test_extract_json_raises_on_non_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_json("Xin lỗi, tôi không thể trả lời.")


def test_response_text_reads_content_attribute() -> None:
    assert response_text(_FakeResponse("hello")) == "hello"


def test_response_text_accepts_plain_string() -> None:
    assert response_text("hello") == "hello"


# --- ainvoke_json -----------------------------------------------------------


async def test_ainvoke_json_returns_first_valid_answer() -> None:
    llm = _FakeLLM('{"ok": true}')
    assert await ainvoke_json(llm, "prompt") == {"ok": True}
    assert len(llm.prompts) == 1


async def test_ainvoke_json_retries_once_with_stricter_instruction() -> None:
    llm = _FakeLLM("không phải JSON", '{"ok": true}')
    assert await ainvoke_json(llm, "prompt") == {"ok": True}
    assert len(llm.prompts) == 2
    assert JSON_RETRY_INSTRUCTION in llm.prompts[1]
    assert llm.prompts[1].startswith("prompt")


async def test_ainvoke_json_appends_user_message_for_chat_prompt() -> None:
    messages = [{"role": "user", "content": "prompt"}]
    llm = _FakeLLM("không phải JSON", '{"ok": true}')
    await ainvoke_json(llm, messages)
    assert llm.prompts[1] == [*messages, {"role": "user", "content": JSON_RETRY_INSTRUCTION}]
    assert messages == [{"role": "user", "content": "prompt"}]  # original prompt not mutated


async def test_ainvoke_json_raises_after_retries_exhausted() -> None:
    llm = _FakeLLM("nope", "still nope")
    with pytest.raises(json.JSONDecodeError):
        await ainvoke_json(llm, "prompt")
    assert len(llm.prompts) == 2


async def test_ainvoke_json_honours_retries_zero() -> None:
    llm = _FakeLLM("nope", '{"ok": true}')
    with pytest.raises(json.JSONDecodeError):
        await ainvoke_json(llm, "prompt", retries=0)
    assert len(llm.prompts) == 1
