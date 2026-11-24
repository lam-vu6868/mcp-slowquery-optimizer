"""
tests/test_llm_groq.py
----------------------

CHỨC NĂNG :
    Kiểm tra adapter Groq bằng API và MCP giả, không dùng key hoặc DB thật.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

THAM KHẢO  : mcp_server/llm/groq.py, docs/api-contract.md (mục 2.3)
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from mcp_server.llm import agent
from mcp_server.llm.agent import analyze_query
from mcp_server.llm.groq import GroqLLMClient

SETTINGS = {
    "model": "openai/gpt-oss-120b", "max_tokens": 2000,
    "temperature": 0.0, "max_tool_calls_per_query": 8, "json_retry": 2,
}
TOOL_NAMES = (
    "get_slow_queries", "get_schema", "get_table_stats",
    "explain_query", "benchmark_query", "apply_optimization",
)


def _groq_choice(content=None, tool_calls=None, finish_reason="stop"):
    """Giả đúng phần phản hồi chat completion mà adapter sử dụng."""
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def _mcp_client():
    """Registry có cả Tool 6 để kiểm tra host vẫn chỉ cấp Tool 1–5."""
    tools = [
        SimpleNamespace(name=name, description=name, input_schema={"type": "object"})
        for name in TOOL_NAMES
    ]
    return SimpleNamespace(
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=tools)),
        call_tool=AsyncMock(return_value=SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(type="text", text=json.dumps({
                "ok": True, "data": {"tables": [{
                    "name": "orders", "columns": [{"name": "status"}], "indexes": [],
                }]}, "meta": {"truncated": False},
            }))],
        )),
    )


@pytest.mark.asyncio
async def test_groq_adapter_passes_tool_result_to_agent_and_parses_index(monkeypatch, tmp_path):
    """Groq tool_calls → Tool 2 → role=tool → JSON cuối → parser."""
    monkeypatch.setattr(agent, "DEFAULT_RUN_DIR", tmp_path)
    call = SimpleNamespace(
        id="call_1", type="function", function=SimpleNamespace(
            name="get_schema", arguments='{"tables":["orders"]}',
        ),
    )
    answer = {
        "query_id": "q07", "diagnosis": "Thiếu index", "confidence": "medium",
        "proposals": [{
            "type": "index", "table": "orders",
            "columns": [{"name": "status", "order": "ASC"}],
            "index_name": "idx_orders_status", "rationale": "Lọc status",
            "target_query_ids": ["q07"],
        }],
    }
    create = AsyncMock(side_effect=[
        _groq_choice(tool_calls=[call], finish_reason="tool_calls"),
        _groq_choice(content=json.dumps(answer)),
    ])
    api = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    mcp = _mcp_client()

    result = await analyze_query(
        "q07", "SELECT * FROM orders WHERE status='paid'",
        llm_client=GroqLLMClient(api), mcp_client=mcp, llm_settings=SETTINGS,
    )

    assert result == answer
    first = create.call_args_list[0].kwargs
    assert first["model"] == SETTINGS["model"]
    assert first["max_completion_tokens"] == 2000
    assert first["messages"][0]["role"] == "system"
    assert {item["function"]["name"] for item in first["tools"]} == (
        set(TOOL_NAMES) - {"apply_optimization"}
    )
    second_messages = create.call_args_list[1].kwargs["messages"]
    assert second_messages[-2]["tool_calls"][0]["function"]["name"] == "get_schema"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "call_1"
    mcp.call_tool.assert_awaited_once_with("get_schema", {"tables": ["orders"]})
    record = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "success"
    assert "paid" not in json.dumps(record)


@pytest.mark.asyncio
async def test_groq_adapter_keeps_json_retry_messages(monkeypatch, tmp_path):
    """JSON sai từ Groq đi qua retry hai lượt của agent hiện tại."""
    monkeypatch.setattr(agent, "DEFAULT_RUN_DIR", tmp_path)
    answer = {"query_id": "q07", "diagnosis": "Chưa đủ dữ liệu", "proposals": [], "confidence": "low"}
    create = AsyncMock(side_effect=[
        _groq_choice(content="not-json"),
        _groq_choice(content=json.dumps(answer)),
    ])
    api = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    result = await analyze_query(
        "q07", "SELECT 1", llm_client=GroqLLMClient(api),
        mcp_client=_mcp_client(), llm_settings=SETTINGS,
    )

    assert result == answer
    messages = create.call_args_list[1].kwargs["messages"]
    assert messages[-2] == {"role": "assistant", "content": "not-json"}
    assert "JSON" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_groq_tool_six_request_is_rejected_before_mcp(monkeypatch, tmp_path):
    """Groq có tự nêu Tool 6 thì host vẫn không chuyển lời gọi sang MCP."""
    monkeypatch.setattr(agent, "DEFAULT_RUN_DIR", tmp_path)
    call = SimpleNamespace(
        id="call_6", type="function", function=SimpleNamespace(
            name="apply_optimization", arguments='{"proposal_id":"p1"}',
        ),
    )
    create = AsyncMock(return_value=_groq_choice(
        tool_calls=[call], finish_reason="tool_calls",
    ))
    api = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    mcp = _mcp_client()

    with pytest.raises(PermissionError, match="apply_optimization"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=GroqLLMClient(api),
            mcp_client=mcp, llm_settings=SETTINGS,
        )

    mcp.call_tool.assert_not_awaited()
    record = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "error"
