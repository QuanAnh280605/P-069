"""Shared helpers for parsing JSON out of LLM text responses.

Every node/service that asks the LLM for JSON should use these helpers so a
weaker model (markdown fences, chatty preamble) degrades the same way
everywhere — and gets one corrective retry before we fall back.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

JSON_RETRY_INSTRUCTION = (
    "Câu trả lời trước không phải JSON hợp lệ. Hãy trả lời lại CHỈ bằng một JSON hợp lệ duy nhất, "
    "không kèm giải thích, không dùng markdown code fence."
)


def strip_code_fence(text: str) -> str:
    """Remove a surrounding ```...``` markdown fence when present."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json(text: str) -> Any:
    """Parse JSON from LLM text, tolerating code fences, surrounding prose, and trailing text.

    Raises:
        json.JSONDecodeError: when no JSON object or array can be recovered.
    """
    cleaned = strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 1. Try raw_decode from whichever delimiter '{' or '[' appears earliest
    candidates = sorted(
        [idx for c in ("{", "[") if (idx := cleaned.find(c)) != -1]
    )
    for start_idx in candidates:
        try:
            obj, _ = json.JSONDecoder().raw_decode(cleaned[start_idx:])
            return obj
        except json.JSONDecodeError:
            pass

    # 2. Try slicing between first and last delimiters (handles messy preamble and postamble)
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("no JSON in LLM response", cleaned, 0)


def response_text(response: Any) -> str:
    """Extract plain text from a LangChain chat response."""
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def _with_retry_instruction(prompt: Any) -> Any:
    """Append the corrective JSON instruction to a str or message-list prompt."""
    if isinstance(prompt, str):
        return f"{prompt}\n\n{JSON_RETRY_INSTRUCTION}"
    if isinstance(prompt, list):
        return [*prompt, {"role": "user", "content": JSON_RETRY_INSTRUCTION}]
    return prompt


async def ainvoke_json(llm: Any, prompt: Any, *, retries: int = 1) -> Any:
    """Invoke the LLM and parse its JSON answer, retrying once when parsing fails.

    Args:
        llm: Any chat model exposing ``ainvoke``.
        prompt: A plain string prompt or a list of chat messages.
        retries: Extra attempts after the first one (default 1).

    Raises:
        json.JSONDecodeError: when the last attempt still returns no JSON.
    """
    current = prompt
    for attempt in range(retries + 1):
        raw = response_text(await llm.ainvoke(current))
        try:
            return extract_json(raw)
        except json.JSONDecodeError:
            if attempt == retries:
                logger.warning("LLM returned non-JSON output after %d attempt(s)", attempt + 1)
                raise
            logger.warning(
                "LLM returned non-JSON output (attempt %d) — retrying with stricter instruction", attempt + 1
            )
            current = _with_retry_instruction(prompt)
    return None
