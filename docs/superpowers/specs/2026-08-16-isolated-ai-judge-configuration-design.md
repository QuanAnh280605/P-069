# Isolated AI Judge Configuration — Design Specification

- **Date:** 2026-08-16
- **Status:** Approved
- **Scope:** Hybrid evaluator AI Judge configuration

## 1. Goal

Prevent the product Agent LLM from evaluating its own generated semantic output by requiring the Hybrid Evaluator's AI Judge to use a separately configured provider, model, and API key.

## 2. Configuration

The existing Agent configuration remains unchanged:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-agent-...
MODEL_NAME=gpt-4o-mini
```

The Judge receives a dedicated configuration:

```env
JUDGE_LLM_PROVIDER=groq
JUDGE_API_KEY=gsk-judge-...
JUDGE_MODEL_NAME=llama-3.3-70b-versatile
JUDGE_API_BASE=https://api.groq.com/openai/v1
```

`JUDGE_API_BASE` may be omitted when the selected Judge provider has a known default endpoint. Judge temperature is fixed at `0.0` in code and is not user-configurable.

## 3. Architecture

`src.services.llm.get_llm()` remains the only LLM construction entrypoint. Its new optional role argument selects either the existing Agent configuration or the dedicated Judge configuration:

```python
get_llm()                 # Agent configuration
get_llm(role="judge")    # Judge configuration
```

`LangChainJudgeLLM` calls `get_llm(role="judge")`; all existing Agent callers continue calling `get_llm()` and therefore require no behavior change.

## 4. Isolation Rules

Judge construction must fail before any network call when any of the following is true:

1. `JUDGE_LLM_PROVIDER`, `JUDGE_API_KEY`, or `JUDGE_MODEL_NAME` is empty.
2. Judge provider equals the normalized Agent provider.
3. Judge model equals the resolved Agent model.
4. Judge API key equals the resolved Agent API key.

There is no fallback from Judge credentials to Agent credentials. Validation errors identify the conflicting field but never include API-key values.

## 5. Provider Resolution

The Agent keeps the current provider-specific key and base-URL resolution. The Judge uses the single dedicated `JUDGE_API_KEY` and `JUDGE_MODEL_NAME`. `JUDGE_API_BASE` overrides the endpoint; otherwise the endpoint is selected from the existing known provider defaults for OpenAI, Gemini, Groq, and MiMo.

Unknown Judge providers require an explicit `JUDGE_API_BASE`. This preserves OpenAI-compatible custom endpoints without weakening credential isolation.

## 6. CLI Behavior

Without `--judge`, no Judge configuration is required and Judge metrics remain `not_applicable`. With `--judge`, `_build_judge_runner()` constructs the dedicated Judge client; invalid isolation configuration stops the run with a clear configuration error before evaluation or API invocation.

CLI help and `.env.example` document the required `JUDGE_*` variables and no longer state that Judge specifically requires `OPENAI_API_KEY`.

## 7. Error Handling and Security

- Judge misconfiguration raises a deterministic configuration error.
- Secrets are never logged or placed in exception messages.
- Existing LLM logging reports only role, provider, model, and base URL.
- Judge output validation, cache, timeout, and retry behavior remain unchanged.

## 8. Testing

Unit tests cover:

- Existing Agent resolution remains backward compatible.
- Valid Judge configuration resolves the dedicated provider, model, key, and endpoint.
- Missing Judge provider, model, or key is rejected.
- Matching Agent/Judge provider is rejected.
- Matching Agent/Judge model is rejected.
- Matching Agent/Judge API key is rejected without exposing the key.
- `LangChainJudgeLLM` requests the `judge` role and reports the configured Judge model.
- CLI parsing and the no-`--judge` path remain unchanged.

All LLM clients are mocked; tests make no external API calls.

## 9. Acceptance Criteria

- Agent and Judge cannot run with the same provider, model, or API key.
- Judge never falls back to an Agent credential.
- Existing Agent callers keep their current behavior.
- Hybrid evaluation without `--judge` needs no Judge variables.
- Hybrid evaluation with `--judge` fails fast on invalid isolation configuration.
- `.env.example` contains a complete, safe Judge configuration example.
