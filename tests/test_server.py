import json

import pytest

from mcp_server import server


@pytest.mark.asyncio
async def test_llm_registry_exposes_only_five_safe_tools():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    assert set(tools) == {
        "get_slow_queries", "get_schema", "get_table_stats",
        "explain_query", "benchmark_query",
    }
    assert set(tools["explain_query"].input_schema["properties"]) == {"sql"}
    assert set(tools["benchmark_query"].input_schema["properties"]) == {"sql"}
    assert "apply_optimization" not in tools


@pytest.mark.asyncio
async def test_registered_tool_reaches_input_validation_without_db(monkeypatch):
    from mcp_server.tools import slow_queries

    monkeypatch.setattr(slow_queries, "get_conn", lambda: pytest.fail("DB must not be called"))
    result = await server.mcp.call_tool("get_slow_queries", {"limit": 0})
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
