"""Tool 6 nằm trong registry Dashboard riêng, không xuất hiện với LLM."""

import json

import pytest

from mcp_server import server
from mcp_server.dashboard_server import make_dashboard_mcp


@pytest.mark.asyncio
async def test_dashboard_registry_exposes_only_tool6_with_two_inputs():
    class FakeApplier:
        def apply_optimization(self, proposal_id, approval_token):
            assert (proposal_id, approval_token) == ("p_abc", "test-token")
            return {"applied": True}

    dashboard_mcp = make_dashboard_mcp(FakeApplier())
    tools = {tool.name: tool for tool in await dashboard_mcp.list_tools()}
    assert set(tools) == {"apply_optimization"}
    assert set(tools["apply_optimization"].input_schema["properties"]) == {
        "proposal_id", "approval_token",
    }
    llm_tools = {tool.name for tool in await server.mcp.list_tools()}
    assert "apply_optimization" not in llm_tools

    result = await dashboard_mcp.call_tool(
        "apply_optimization", {"proposal_id": "p_abc", "approval_token": "test-token"},
    )
    assert json.loads(result.content[0].text) == {"applied": True}
