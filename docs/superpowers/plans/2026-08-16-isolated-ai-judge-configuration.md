# Isolated AI Judge Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure the Hybrid Evaluator's AI Judge with a provider, model, and API key that are all mandatory and different from the product Agent LLM.

**Architecture:** Keep `src.services.llm.get_llm()` as the only client factory and add a role selector whose default preserves all Agent callers. The Judge role resolves only dedicated `JUDGE_*` settings, validates isolation before client construction, and is consumed explicitly by `LangChainJudgeLLM`.

**Tech Stack:** Python 3.11+, Pydantic Settings, LangChain OpenAI-compatible client, Pytest, Ruff.

## Global Constraints

- `JUDGE_LLM_PROVIDER`, `JUDGE_API_KEY`, and `JUDGE_MODEL_NAME` are mandatory only when the Judge role is requested.
- Judge provider, model, and API key must each differ from the resolved Agent values.
- Judge credentials never fall back to Agent credentials and never appear in logs or exceptions.
- Judge temperature is fixed at `0.0`.
- All LLM construction continues through `get_llm()` in `src/services/llm.py`.
- Public functions have English docstrings, full type hints, and stay within 30 lines.
- Tests mock LLM clients and make no external API calls.

---

### Task 1: Add role-aware LLM configuration and strict Judge isolation

**Files:**
- Modify: `src/config.py:23-38`
- Modify: `src/services/llm.py:23-84`
- Create: `tests/test_services/test_llm.py`

**Interfaces:**
- Produces: `LLMRole = Literal["agent", "judge"]`.
- Produces: `_resolve_llm_config(settings: Settings, role: LLMRole = "agent") -> tuple[str, str, str]`.
- Produces: `get_llm(role: LLMRole = "agent") -> ChatOpenAI`.
- Preserves: every existing no-argument `get_llm()` call resolves the Agent configuration exactly as before.

- [ ] **Step 1: Write failing resolver tests**

Create `tests/test_services/test_llm.py` with explicit settings that ignore the developer's local `.env`:

```python
from unittest.mock import patch

import pytest

from src.config import Settings
from src.services.llm import _resolve_llm_config, get_llm


def _settings(**overrides: str) -> Settings:
    values = {
        "llm_provider": "openai",
        "openai_api_key": "agent-secret",
        "model_name": "gpt-4o-mini",
        "judge_llm_provider": "groq",
        "judge_api_key": "judge-secret",
        "judge_model_name": "llama-3.3-70b-versatile",
        "judge_api_base": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_agent_resolution_remains_default() -> None:
    assert _resolve_llm_config(_settings()) == (
        "agent-secret",
        "https://api.openai.com/v1",
        "gpt-4o-mini",
    )


def test_judge_resolution_uses_dedicated_values() -> None:
    assert _resolve_llm_config(_settings(), role="judge") == (
        "judge-secret",
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile",
    )


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("judge_llm_provider", "JUDGE_LLM_PROVIDER is required"),
        ("judge_api_key", "JUDGE_API_KEY is required"),
        ("judge_model_name", "JUDGE_MODEL_NAME is required"),
    ),
)
def test_judge_rejects_missing_required_setting(field: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _resolve_llm_config(_settings(**{field: ""}), role="judge")


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"judge_llm_provider": "OPENAI"}, "provider must differ"),
        ({"judge_model_name": "GPT-4O-MINI"}, "model must differ"),
        ({"judge_api_key": "agent-secret"}, "API key must differ"),
    ),
)
def test_judge_rejects_agent_identity(overrides: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message) as raised:
        _resolve_llm_config(_settings(**overrides), role="judge")
    assert "agent-secret" not in str(raised.value)
    assert "judge-secret" not in str(raised.value)


def test_unknown_judge_provider_requires_base_url() -> None:
    with pytest.raises(ValueError, match="JUDGE_API_BASE is required"):
        _resolve_llm_config(_settings(judge_llm_provider="custom"), role="judge")


def test_get_llm_builds_judge_with_zero_temperature() -> None:
    settings = _settings()
    with patch("src.services.llm.get_settings", return_value=settings), patch(
        "src.services.llm.ChatOpenAI"
    ) as client:
        get_llm(role="judge")
    client.assert_called_once_with(
        model="llama-3.3-70b-versatile",
        api_key="judge-secret",
        temperature=0.0,
        base_url="https://api.groq.com/openai/v1",
    )
```

- [ ] **Step 2: Run tests and verify the new contract fails**

Run: `pytest tests/test_services/test_llm.py -q`

Expected: FAIL because the Judge settings and `role` arguments do not exist yet.

- [ ] **Step 3: Add dedicated Judge settings**

Add these fields to `Settings` in `src/config.py` after the Agent LLM fields:

```python
    # AI Judge uses an isolated provider, credential, and model.
    judge_llm_provider: str = ""
    judge_api_key: str = ""
    judge_model_name: str = ""
    judge_api_base: str = ""
```

- [ ] **Step 4: Implement role-aware resolution and validation**

Refactor `src/services/llm.py` into small helpers while keeping Agent behavior stable:

```python
from typing import Any, Literal

LLMRole = Literal["agent", "judge"]


def _judge_config(settings: Settings) -> tuple[str, str, str]:
    provider = settings.judge_llm_provider.strip().lower()
    required = (
        (provider, "JUDGE_LLM_PROVIDER is required"),
        (settings.judge_api_key.strip(), "JUDGE_API_KEY is required"),
        (settings.judge_model_name.strip(), "JUDGE_MODEL_NAME is required"),
    )
    for value, message in required:
        if not value:
            raise ValueError(message)
    base_url = settings.judge_api_base.strip() or _provider_base_url(settings, provider)
    if not base_url:
        raise ValueError("JUDGE_API_BASE is required for an unknown Judge provider")
    return settings.judge_api_key.strip(), base_url, settings.judge_model_name.strip()


def _validate_judge_isolation(
    settings: Settings,
    agent: tuple[str, str, str],
    judge: tuple[str, str, str],
) -> None:
    if settings.judge_llm_provider.strip().casefold() == settings.llm_provider.strip().casefold():
        raise ValueError("Judge provider must differ from Agent provider")
    if judge[2].casefold() == agent[2].strip().casefold():
        raise ValueError("Judge model must differ from Agent model")
    if judge[0] == agent[0].strip():
        raise ValueError("Judge API key must differ from Agent API key")


def _resolve_llm_config(
    settings: Settings,
    role: LLMRole = "agent",
) -> tuple[str, str, str]:
    agent = _agent_config(settings)
    if role == "agent":
        return agent
    judge = _judge_config(settings)
    _validate_judge_isolation(settings, agent, judge)
    return judge
```

Extract the current logic into `_agent_config(settings)` and common endpoint lookup into `_provider_base_url(settings, provider)`. Update the factory without introducing a second LLM constructor:

```python
def get_llm(role: LLMRole = "agent") -> ChatOpenAI:
    """Instantiate an Agent or isolated Judge LLM client."""
    settings = get_settings()
    api_key, base_url, model_name = _resolve_llm_config(settings, role)
    temperature = 0.0 if role == "judge" else settings.llm_temperature
    logger.info(
        "Instantiating LLM client (role=%s, provider=%s, model=%s, base_url=%s)",
        role,
        settings.judge_llm_provider if role == "judge" else settings.llm_provider,
        model_name,
        base_url or "default",
    )
    kwargs: dict[str, Any] = {"model": model_name, "api_key": api_key, "temperature": temperature}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
```

- [ ] **Step 5: Run the focused tests**

Run: `pytest tests/test_services/test_llm.py -q`

Expected: all tests PASS and no network call occurs.

- [ ] **Step 6: Run existing Agent LLM consumer tests**

Run: `pytest tests/test_agents/test_enrich_node.py tests/test_agents/test_on_demand_metric_suggest_node.py tests/test_services/test_metric_generator.py tests/test_services/test_semantic_service.py -q`

Expected: PASS, proving no-argument `get_llm()` remains compatible.

- [ ] **Step 7: Commit the role-aware configuration**

```bash
git add src/config.py src/services/llm.py tests/test_services/test_llm.py
git commit -m "feat: isolate AI judge LLM configuration"
```

---

### Task 2: Connect Hybrid Judge and CLI to the isolated role

**Files:**
- Modify: `eval/evaluator/hybrid/judge/base.py:24-40`
- Modify: `eval/run_eval.py:61-77`
- Modify: `tests/test_evaluation/hybrid/test_judge_base.py`
- Modify: `tests/test_evaluation/test_run_eval_cli.py`

**Interfaces:**
- Consumes: `get_llm(role: LLMRole = "agent") -> ChatOpenAI` from Task 1.
- Produces: `LangChainJudgeLLM` whose client always comes from `get_llm(role="judge")`.
- Preserves: Hybrid runs without `--judge` do not construct or validate a Judge client.

- [ ] **Step 1: Write failing Judge-adapter tests**

Append to `tests/test_evaluation/hybrid/test_judge_base.py`:

```python
from types import SimpleNamespace
from unittest.mock import patch

from eval.evaluator.hybrid.judge.base import LangChainJudgeLLM


def test_langchain_judge_requests_isolated_role() -> None:
    client = SimpleNamespace(model_name="judge-model")
    with patch("src.services.llm.get_llm", return_value=client) as factory:
        judge = LangChainJudgeLLM()
    factory.assert_called_once_with(role="judge")
    assert judge.model_name == "judge-model"
```

Add to `tests/test_evaluation/test_run_eval_cli.py`:

```python
async def test_hybrid_without_judge_does_not_build_judge(mini_dataset, tmp_path, monkeypatch) -> None:
    dataset = _executable_dataset(mini_dataset, tmp_path)

    async def _load(golden_root: Path, domain: str) -> DomainDataset:
        return dataset

    def _unexpected() -> None:
        raise AssertionError("Judge must not be built without --judge")

    monkeypatch.setattr("eval.run_eval.load_domain_dataset", _load)
    monkeypatch.setattr("eval.run_eval._build_judge_runner", _unexpected)
    args = parse_args(["--engine", "hybrid", "--report-dir", str(tmp_path / "reports")])
    exit_code = await run_hybrid_engine(args)
    assert exit_code == 0
```

- [ ] **Step 2: Run the adapter tests and verify failure**

Run: `pytest tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/test_run_eval_cli.py -q`

Expected: the adapter test FAILS because `LangChainJudgeLLM` still calls `get_llm()` without a role.

- [ ] **Step 3: Switch the Judge adapter to the isolated role**

Update `LangChainJudgeLLM.__init__`:

```python
    def __init__(self) -> None:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.services.llm import get_llm

        self._llm = get_llm(role="judge")
        self._message_types = (SystemMessage, HumanMessage)
        self.model_name = str(self._llm.model_name)
```

Update the `--judge` help and runner docstring in `eval/run_eval.py`:

```python
    parser.add_argument(
        "--judge",
        action="store_true",
        help="enable the isolated AI Judge lane (requires JUDGE_* configuration)",
    )
```

- [ ] **Step 4: Run all Hybrid Judge and CLI tests**

Run: `pytest tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/hybrid/test_judge_metrics.py tests/test_evaluation/test_run_eval_cli.py -q`

Expected: PASS with fake/mocked LLMs only.

- [ ] **Step 5: Commit the Judge integration**

```bash
git add eval/evaluator/hybrid/judge/base.py eval/run_eval.py tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/test_run_eval_cli.py
git commit -m "feat: route hybrid judge through isolated LLM"
```

---

### Task 3: Document the dedicated Judge environment contract

**Files:**
- Modify: `.env.example:7-31`
- Modify: `eval/README.md:170-190`

**Interfaces:**
- Documents: `JUDGE_LLM_PROVIDER`, `JUDGE_API_KEY`, `JUDGE_MODEL_NAME`, and optional `JUDGE_API_BASE`.
- Documents: all three Judge identity values must differ from the Agent values.

- [ ] **Step 1: Add the complete environment example**

Add after the Agent LLM section in `.env.example`:

```env
# ---- AI Judge Configuration ----
# Required only with: python -m eval.run_eval --engine hybrid --judge
# Provider, model, and API key must all differ from the Agent configuration above.
JUDGE_LLM_PROVIDER=groq
JUDGE_API_KEY=gsk-your-separate-judge-key-here
JUDGE_MODEL_NAME=llama-3.3-70b-versatile
# Optional for known providers; required for a custom OpenAI-compatible provider.
# JUDGE_API_BASE=https://api.groq.com/openai/v1
```

- [ ] **Step 2: Explain isolation and failure behavior in the evaluator README**

Add this paragraph to the Hybrid section in `eval/README.md`:

```markdown
`--judge` uses the dedicated `JUDGE_*` configuration. Judge provider, model,
and API key must each differ from the Agent LLM; missing or matching values
stop the run before any API call. There is no fallback to Agent credentials.
Judge temperature is always `0.0`.
```

- [ ] **Step 3: Check documentation consistency**

Run: `rg -n "requires OPENAI_API_KEY|JUDGE_LLM_PROVIDER|JUDGE_API_KEY|JUDGE_MODEL_NAME|JUDGE_API_BASE" .env.example eval/README.md eval/run_eval.py`

Expected: no obsolete `requires OPENAI_API_KEY` text and all four `JUDGE_*` names appear consistently.

- [ ] **Step 4: Commit the environment documentation**

```bash
git add .env.example eval/README.md
git commit -m "docs: document isolated AI judge settings"
```

---

### Task 4: Run formatting and complete verification

**Files:**
- Verify: `src/config.py`
- Verify: `src/services/llm.py`
- Verify: `eval/evaluator/hybrid/judge/base.py`
- Verify: `eval/run_eval.py`
- Verify: `tests/test_services/test_llm.py`
- Verify: `tests/test_evaluation/hybrid/test_judge_base.py`
- Verify: `tests/test_evaluation/test_run_eval_cli.py`

**Interfaces:**
- Consumes: all implementation and documentation from Tasks 1-3.
- Produces: evidence that isolation, compatibility, lint, and formatting requirements pass together.

- [ ] **Step 1: Format only the touched Python files**

Run: `ruff format src/config.py src/services/llm.py eval/evaluator/hybrid/judge/base.py eval/run_eval.py tests/test_services/test_llm.py tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/test_run_eval_cli.py`

Expected: command exits successfully and changes only formatting in the listed files.

- [ ] **Step 2: Run the required source lint**

Run: `ruff check src/`

Expected: PASS with no violations.

- [ ] **Step 3: Lint the touched evaluator and test files**

Run: `ruff check eval/evaluator/hybrid/judge/base.py eval/run_eval.py tests/test_services/test_llm.py tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/test_run_eval_cli.py`

Expected: PASS with no violations.

- [ ] **Step 4: Run the focused isolation suite**

Run: `pytest tests/test_services/test_llm.py tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/hybrid/test_judge_metrics.py tests/test_evaluation/test_run_eval_cli.py -q`

Expected: PASS with no external LLM calls.

- [ ] **Step 5: Run the complete Hybrid evaluation suite**

Run: `pytest tests/test_evaluation/hybrid tests/test_evaluation/test_run_eval_cli.py -q`

Expected: PASS, confirming deterministic scoring, Judge behavior, reporting, and CLI compatibility.

- [ ] **Step 6: Inspect the final diff and repository status**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intended implementation files and pre-existing Hybrid worktree changes are listed.

- [ ] **Step 7: Commit any verification-only formatting changes**

If Step 1 produced formatting changes not included in prior commits:

```bash
git add src/config.py src/services/llm.py eval/evaluator/hybrid/judge/base.py eval/run_eval.py tests/test_services/test_llm.py tests/test_evaluation/hybrid/test_judge_base.py tests/test_evaluation/test_run_eval_cli.py
git commit -m "style: format isolated judge configuration"
```
