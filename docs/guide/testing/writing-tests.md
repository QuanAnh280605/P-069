---
title: "Writing Tests"
description: "Cach viet tests cho P-069 Semantic Layer Agent"
weight: 1
---

## Test Structure

```
tests/
├── conftest.py              ← Fixtures dung chung (async_session, client, mock_llm)
├── test_auth.py             ← Auth unit + integration tests
├── test_agents/
│   └── test_graph.py        ← AgentState + node tests
├── test_api/
│   └── test_routes.py       ← API endpoint tests
└── test_models/
    └── test_db_models.py    ← ORM model + Fernet encryption tests
```

## API Tests

```python
import pytest

@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_generate_requires_db_id(client):
    response = await client.post("/api/v1/semantic/generate", json={})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_export_invalid_format(client):
    response = await client.get("/api/v1/semantic/1/export?format=csv")
    assert response.status_code == 400
```

## Agent Tests

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_agent_state_has_required_fields():
    from src.agents.state import AgentState
    fields = AgentState.__annotations__
    assert "db_id" in fields
    assert "raw_schema" in fields
    assert "enriched_schema" in fields
    assert "suggested_metrics" in fields

@pytest.mark.asyncio
async def test_introspect_node_returns_raw_schema():
    with patch("src.agents.nodes.introspect_node.introspect_node", new_callable=AsyncMock) as mock:
        mock.return_value = {"raw_schema": {"users": {"columns": []}}}
        result = await mock(state={"db_id": 1})
        assert "raw_schema" in result
```

## Run Tests

```bash
# Run all
pytest tests/ -v

# Specific file
pytest tests/test_api/test_routes.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## Minimum Requirements

- Toi thieu 3 test cases cho API
- Toi thieu 2 test cases cho Agent
- Mock LLM trong tests - khong goi OpenAI API that
- Mock DB - dung SQLite in-memory
- Tat ca tests phai pass truoc khi push
