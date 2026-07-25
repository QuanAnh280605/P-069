import pytest

from src.agents.graph import agent, should_continue
from src.agents.nodes.example_node import analyze_node, respond_node

# --- analyze_node tests ---


@pytest.mark.asyncio
async def test_analyze_node_returns_analysis():
    state = {"query": "What is Python?"}
    result = await analyze_node(state)
    assert "analysis" in result
    assert "What is Python?" in result["analysis"]


@pytest.mark.asyncio
async def test_analyze_node_empty_query():
    state = {"query": ""}
    result = await analyze_node(state)
    assert "analysis" in result
    assert result["analysis"] == "Phân tích: "


@pytest.mark.asyncio
async def test_analyze_node_missing_query():
    state = {}
    result = await analyze_node(state)
    assert "analysis" in result
    assert result["analysis"] == "Phân tích: "


@pytest.mark.asyncio
async def test_analyze_node_preserves_query_in_output():
    query = "Explain machine learning algorithms"
    state = {"query": query}
    result = await analyze_node(state)
    assert query in result["analysis"]


# --- respond_node tests ---


@pytest.mark.asyncio
async def test_respond_node_returns_response():
    state = {"analysis": "Test analysis"}
    result = await respond_node(state)
    assert "response" in result
    assert "Test analysis" in result["response"]


@pytest.mark.asyncio
async def test_respond_node_with_error():
    state = {"error": "Something went wrong"}
    result = await respond_node(state)
    assert "response" in result
    assert "Lỗi: Something went wrong" in result["response"]


@pytest.mark.asyncio
async def test_respond_node_error_overrides_analysis():
    state = {"analysis": "Good analysis", "error": "Fatal error"}
    result = await respond_node(state)
    assert "Lỗi:" in result["response"]
    assert "Good analysis" not in result["response"]


@pytest.mark.asyncio
async def test_respond_node_empty_state():
    state = {}
    result = await respond_node(state)
    assert "response" in result
    assert "Kết quả dựa trên phân tích:" in result["response"]


# --- should_continue routing tests ---


def test_should_continue_with_error():
    state = {"error": "Some error"}
    result = should_continue(state)
    assert result == "__end__"


def test_should_continue_without_error():
    state = {"analysis": "Some analysis"}
    result = should_continue(state)
    assert result == "respond"


def test_should_continue_empty_state():
    state = {}
    result = should_continue(state)
    assert result == "respond"


def test_should_continue_error_empty_string():
    state = {"error": ""}
    result = should_continue(state)
    assert result == "respond"  # empty string is falsy


# --- Full agent graph tests ---


@pytest.mark.asyncio
async def test_agent_basic_flow():
    result = await agent.ainvoke({"query": "Hello"})
    assert "response" in result


@pytest.mark.asyncio
async def test_agent_state_structure():
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result


@pytest.mark.asyncio
async def test_agent_full_pipeline():
    result = await agent.ainvoke({"query": "Explain AI"})
    assert result["query"] == "Explain AI"
    assert "analysis" in result
    assert "response" in result
    assert "Explain AI" in result["analysis"]
    assert "Phân tích:" in result["analysis"]
    assert "Kết quả dựa trên phân tích:" in result["response"]


@pytest.mark.asyncio
async def test_agent_preserves_query():
    query = "What is deep learning?"
    result = await agent.ainvoke({"query": query})
    assert result["query"] == query
