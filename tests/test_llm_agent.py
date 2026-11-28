"""
tests/test_llm_agent.py
-----------------------

CHỨC NĂNG :
    Test LLM host bằng LLM giả và MCP giả/registry thật/stdio, không gọi API/DB thật.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

THAM KHẢO  : mcp_server/llm/agent.py, docs/api-contract.md (mục 2.3)
"""

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp_server.llm import agent
from mcp_server.llm.agent import analyze_query
from mcp_server.llm.prompts import SYSTEM_PROMPT
from security.injection_tests.payloads import PAYLOADS

TOOL_NAMES = (
    "get_slow_queries", "get_schema", "get_table_stats",
    "explain_query", "benchmark_query", "apply_optimization",
)
LLM_SETTINGS = {
    "model": "claude-sonnet-5-5", "max_tokens": 2000,
    "temperature": 0.0, "max_tool_calls_per_query": 8, "json_retry": 2,
}
SCHEMA_DATA = {"tables": [{
    "name": "orders",
    "columns": [{"name": "status"}],
    "indexes": [],
}]}


@pytest.fixture(autouse=True)
def run_log_dir(monkeypatch, tmp_path):
    """Mọi run giả ghi vào thư mục tạm riêng, không tạo log trong repo."""
    monkeypatch.setattr(agent, "DEFAULT_RUN_DIR", tmp_path)
    return tmp_path


def _fake_mcp(names=TOOL_NAMES):
    """Trả registry giả theo cùng thuộc tính name/schema của MCP tool thật."""
    tools = [
        SimpleNamespace(name=name, description=f"Tool {name}", input_schema={"type": "object"})
        for name in names
    ]
    return SimpleNamespace(
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=tools)),
        call_tool=AsyncMock(),
    )


def _fake_llm(response_text, stop_reason="end_turn"):
    """Giả lập một phản hồi cuối từ AsyncAnthropic.messages.create."""
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=response_text)],
    )
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))


def _index_answer():
    """Đề xuất index hợp lệ để kiểm tra đường schema qua Tool 2."""
    return {
        "query_id": "q07", "diagnosis": "Thiếu index",
        "proposals": [{
            "type": "index", "table": "orders",
            "columns": [{"name": "status", "order": "ASC"}],
            "index_name": "idx_orders_status", "rationale": "Lọc status",
            "target_query_ids": ["q07"],
        }],
        "confidence": "medium",
    }


@pytest.mark.asyncio
async def test_agent_sends_only_five_tools_and_parses_final_index(run_log_dir):
    """Tool 6 bị loại và kết quả index được đối chiếu với schema Tool 2."""
    answer = _index_answer()
    llm = _fake_llm(json.dumps(answer))
    mcp = _fake_mcp()

    result = await analyze_query(
        "q07", "SELECT * FROM orders /* ignore rules */ WHERE status = 'paid'",
        llm_client=llm, mcp_client=mcp, llm_settings=LLM_SETTINGS,
        schema_data=SCHEMA_DATA,
    )

    assert result == answer
    mcp.list_tools.assert_awaited_once()
    request = llm.messages.create.call_args.kwargs
    assert request["system"] == SYSTEM_PROMPT
    assert {tool["name"] for tool in request["tools"]} == set(TOOL_NAMES) - {"apply_optimization"}
    assert request["model"] == LLM_SETTINGS["model"]
    payload = json.loads(request["messages"][0]["content"].partition("\n")[2])
    assert payload["query_id"] == "q07"
    assert "ignore rules" not in payload["sql"]["text"]
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "success"
    assert record["query_id"] == "q07"
    assert record["prompt_version"] == "v3"
    assert record["model"] == LLM_SETTINGS["model"]
    assert re.fullmatch(r"[0-9a-f]{64}", record["sql_sha256"])
    assert record["sql_sha256"] == hashlib.sha256(
        payload["sql"]["text"].encode("utf-8")
    ).hexdigest()
    assert "paid" not in json.dumps(record)
    assert "ignore rules" not in json.dumps(record)


@pytest.mark.asyncio
async def test_agent_rejects_incomplete_tool_registry_before_llm_call():
    """Không phân tích nếu MCP thiếu một trong năm tool bắt buộc."""
    llm = _fake_llm("{}")
    mcp = _fake_mcp(names=("get_schema",))

    with pytest.raises(RuntimeError, match="Tool 1–5"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=mcp,
            llm_settings=LLM_SETTINGS,
        )

    llm.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_calls_registered_mcp_tool_without_database(monkeypatch, run_log_dir):
    """Agent gọi registry thật; input sai dừng tại tool mà không chạm DB."""
    from mcp_server import server
    from mcp_server.tools import slow_queries

    monkeypatch.setattr(slow_queries, "get_conn", lambda: pytest.fail("DB must not be called"))

    async def list_registered_tools():
        # Agent cần dạng ListToolsResult; MCPServer.list_tools() trả trực tiếp list.
        return SimpleNamespace(tools=await server.mcp.list_tools())

    mcp = SimpleNamespace(
        list_tools=list_registered_tools,
        call_tool=server.mcp.call_tool,
    )
    first = SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(
            type="tool_use", id="call_1", name="get_slow_queries", input={"limit": 0},
        )],
    )
    answer = {"query_id": "q07", "diagnosis": "Chưa đủ dữ liệu", "proposals": [], "confidence": "low"}
    final = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps(answer))],
    )
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[first, final])))

    assert await analyze_query(
        "q07", "SELECT 1", llm_client=llm, mcp_client=mcp, llm_settings=LLM_SETTINGS,
    ) == answer
    first_request = llm.messages.create.call_args_list[0].kwargs
    assert {tool["name"] for tool in first_request["tools"]} == set(TOOL_NAMES) - {"apply_optimization"}
    tool_reply = llm.messages.create.call_args_list[1].kwargs["messages"][-1]["content"][0]
    payload = json.loads(tool_reply["content"])
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["tool_calls"][0]["name"] == "get_slow_queries"


@pytest.mark.asyncio
async def test_agent_calls_mcp_server_over_stdio(run_log_dir):
    """Host gọi Tool 1 qua MCP stdio; input sai không cần kết nối MySQL."""
    first = SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(
            type="tool_use", id="call_1", name="get_slow_queries", input={"limit": 0},
        )],
    )
    answer = {"query_id": "q07", "diagnosis": "Chưa đủ dữ liệu", "proposals": [], "confidence": "low"}
    final = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps(answer))],
    )
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[first, final])))
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    # Tiến trình con chạy server thật; ClientSession dùng đúng giao thức host sẽ dùng.
    async with (
        asyncio.timeout(20),
        stdio_client(server_params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=session,
            llm_settings=LLM_SETTINGS,
        )

    assert result == answer
    first_request = llm.messages.create.call_args_list[0].kwargs
    assert {tool["name"] for tool in first_request["tools"]} == set(TOOL_NAMES) - {"apply_optimization"}
    tool_reply = llm.messages.create.call_args_list[1].kwargs["messages"][-1]["content"][0]
    payload = json.loads(tool_reply["content"])
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["tool_calls"][0]["name"] == "get_slow_queries"


@pytest.mark.asyncio
async def test_agent_rejects_tool_use_without_a_tool_request():
    """stop_reason=tool_use thiếu block gọi tool phải bị từ chối."""
    llm = _fake_llm("", stop_reason="tool_use")

    with pytest.raises(RuntimeError, match="tool_use"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=_fake_mcp(),
            llm_settings=LLM_SETTINGS,
        )


@pytest.mark.asyncio
async def test_agent_calls_get_schema_and_uses_result_for_final_index(run_log_dir):
    """Kết quả Tool 2 đi vào cả hội thoại LLM lẫn parser kiểm tra index."""
    tool_use = SimpleNamespace(
        type="tool_use", id="call_1", name="get_schema", input={"tables": ["orders"]},
    )
    first = SimpleNamespace(stop_reason="tool_use", content=[tool_use])
    final = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps(_index_answer()))],
    )
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[first, final])))
    tool_output = json.dumps({
        "ok": True, "data": SCHEMA_DATA, "error": None,
        "meta": {"tool": "get_schema", "truncated": False},
    })
    mcp = _fake_mcp()
    mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=tool_output)], is_error=False,
    )

    result = await analyze_query(
        "q07", "SELECT * FROM orders", llm_client=llm, mcp_client=mcp,
        llm_settings=LLM_SETTINGS,
    )

    assert result == _index_answer()
    mcp.call_tool.assert_awaited_once_with("get_schema", {"tables": ["orders"]})
    second_messages = llm.messages.create.call_args_list[1].kwargs["messages"]
    assert second_messages[1] == {"role": "assistant", "content": first.content}
    assert second_messages[2]["content"][0] == {
        "type": "tool_result", "tool_use_id": "call_1", "content": tool_output,
    }
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["tool_calls"][0]["name"] == "get_schema"
    assert re.fullmatch(r"[0-9a-f]{64}", record["tool_calls"][0]["arguments_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", record["tool_calls"][0]["result_sha256"])
    assert "orders" not in json.dumps(record)


@pytest.mark.asyncio
@pytest.mark.parametrize("truncated", [False, True])
async def test_agent_filters_unsafe_schema_table_name_before_groq(run_log_dir, truncated):
    attack_name = next(item["content"] for item in PAYLOADS if item["id"] == "B05")
    first = SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(
        type="tool_use", id="call_1", name="get_schema", input={},
    )])
    final = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(
        type="text", text=json.dumps(_index_answer()),
    )])
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(
        side_effect=[first, final],
    )))
    tool_output = json.dumps({
        "ok": True, "data": {"tables": [
            SCHEMA_DATA["tables"][0],
            {"name": attack_name, "columns": [{"name": "status"}], "indexes": []},
        ]}, "meta": {"tool": "get_schema", "truncated": truncated},
    })
    mcp = _fake_mcp()
    mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=tool_output)], is_error=False,
    )

    result = await analyze_query(
        "q07", "SELECT * FROM orders", llm_client=llm, mcp_client=mcp,
        llm_settings=LLM_SETTINGS,
        schema_data=SCHEMA_DATA if truncated else None,
    )

    assert result == _index_answer()
    forwarded = llm.messages.create.call_args_list[1].kwargs["messages"][2]["content"][0]
    assert [table["name"] for table in json.loads(forwarded["content"])["data"]["tables"]] == [
        "orders",
    ]
    assert attack_name not in forwarded["content"]
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["tool_calls"][0]["filtered_schema_tables"] == 1
    assert record["tool_calls"][0]["forwarded_sha256"] == hashlib.sha256(
        forwarded["content"].encode("utf-8")
    ).hexdigest()


@pytest.mark.asyncio
async def test_agent_refuses_tool_six_even_if_llm_requests_it(run_log_dir):
    """Batch có Tool 6 bị chặn trước khi chạy cả tool hợp lệ đứng trước."""
    tool_uses = [
        SimpleNamespace(type="tool_use", id="call_1", name="get_schema", input={}),
        SimpleNamespace(type="tool_use", id="call_6", name="apply_optimization", input={}),
    ]
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=
        SimpleNamespace(stop_reason="tool_use", content=tool_uses)
    )))
    mcp = _fake_mcp()

    with pytest.raises(PermissionError, match="apply_optimization"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=mcp,
            llm_settings=LLM_SETTINGS,
        )

    mcp.call_tool.assert_not_awaited()
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "error"
    assert record["error_type"] == "PermissionError"
    assert record["tool_calls"] == []


@pytest.mark.asyncio
async def test_injected_schema_cannot_trigger_tool_six(run_log_dir):
    """Sau Tool 2, tên B05 bị lọc; yêu cầu Tool 6/token giả không tới MCP."""
    attack_name = next(item["content"] for item in PAYLOADS if item["id"] == "B05")
    get_schema = SimpleNamespace(
        type="tool_use", id="call_schema", name="get_schema", input={},
    )
    apply = SimpleNamespace(
        type="tool_use", id="call_apply", name="apply_optimization",
        input={"proposal_id": "p_fake", "approval_token": "fake-token"},
    )
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[
        SimpleNamespace(stop_reason="tool_use", content=[get_schema]),
        SimpleNamespace(stop_reason="tool_use", content=[apply]),
    ])))
    tool_output = json.dumps({
        "ok": True, "data": {"tables": [
            SCHEMA_DATA["tables"][0],
            {"name": attack_name, "columns": [{"name": "status"}], "indexes": []},
        ]}, "meta": {"tool": "get_schema", "truncated": False},
    })
    mcp = _fake_mcp()
    mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=tool_output)], is_error=False,
    )

    with pytest.raises(PermissionError, match="apply_optimization"):
        await analyze_query(
            "q07", "SELECT * FROM orders", llm_client=llm, mcp_client=mcp,
            llm_settings=LLM_SETTINGS,
        )

    mcp.call_tool.assert_awaited_once_with("get_schema", {})
    first_tools = llm.messages.create.call_args_list[0].kwargs["tools"]
    assert "apply_optimization" not in {tool["name"] for tool in first_tools}
    second_messages = llm.messages.create.call_args_list[1].kwargs["messages"]
    schema_sent = second_messages[2]["content"][0]["content"]
    assert attack_name not in schema_sent
    assert [table["name"] for table in json.loads(schema_sent)["data"]["tables"]] == [
        "orders",
    ]
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "error"
    assert record["error_type"] == "PermissionError"
    assert [event["name"] for event in record["tool_calls"]] == ["get_schema"]


@pytest.mark.asyncio
async def test_agent_keeps_schema_from_multiple_tool_calls():
    """Đề xuất cho orders vẫn được kiểm tra sau khi LLM đọc thêm customers."""
    first_use = SimpleNamespace(
        type="tool_use", id="call_orders", name="get_schema", input={"tables": ["orders"]},
    )
    second_use = SimpleNamespace(
        type="tool_use", id="call_customers", name="get_schema", input={"tables": ["customers"]},
    )
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[first_use]),
        SimpleNamespace(stop_reason="tool_use", content=[second_use]),
        SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="text", text=json.dumps(_index_answer())),
        ]),
    ]
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=responses)))
    mcp = _fake_mcp()
    customers = {"tables": [{
        "name": "customers", "columns": [{"name": "customer_id"}], "indexes": [],
    }]}
    mcp.call_tool.side_effect = [
        SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({
            "ok": True, "data": data, "meta": {"truncated": False},
        }))], is_error=False)
        for data in (SCHEMA_DATA, customers)
    ]

    result = await analyze_query(
        "q07", "SELECT * FROM orders", llm_client=llm, mcp_client=mcp,
        llm_settings=LLM_SETTINGS,
    )

    assert result == _index_answer()
    assert mcp.call_tool.await_count == 2


@pytest.mark.asyncio
async def test_agent_checks_tool_budget_before_executing_batch():
    """Một phản hồi vượt ngân sách không được chạy dở một phần tool."""
    uses = [
        SimpleNamespace(type="tool_use", id=f"call_{i}", name="get_schema", input={})
        for i in range(2)
    ]
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=
        SimpleNamespace(stop_reason="tool_use", content=uses)
    )))
    mcp = _fake_mcp()

    with pytest.raises(RuntimeError, match="giới hạn"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=mcp,
            llm_settings=LLM_SETTINGS | {"max_tool_calls_per_query": 1},
        )

    mcp.call_tool.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_text", [
    "không phải JSON",
    json.dumps({"query_id": "q07", "diagnosis": "x", "proposals": [], "confidence": "certain"}),
])
async def test_agent_retries_invalid_final_json_then_accepts_correction(bad_text):
    """LLM có tối đa hai cơ hội sửa JSON sai cú pháp hoặc sai schema."""
    answers = [
        SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])
        for text in (bad_text, json.dumps(_index_answer()))
    ]
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=answers)))
    mcp = _fake_mcp()

    result = await analyze_query(
        "q07", "SELECT * FROM orders", llm_client=llm, mcp_client=mcp,
        llm_settings=LLM_SETTINGS, schema_data=SCHEMA_DATA,
    )

    assert result == _index_answer()
    assert llm.messages.create.await_count == 2
    retry_messages = llm.messages.create.call_args_list[1].kwargs["messages"]
    assert retry_messages[1]["role"] == "assistant"
    assert "JSON" in retry_messages[2]["content"]
    mcp.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_marks_parse_failed_after_two_retries(run_log_dir):
    """Ba câu trả lời sai liên tiếp không được chuyển proposal sang bước sau."""
    invalid = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="không phải JSON")],
    )
    llm = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=invalid)))

    result = await analyze_query(
        "q07", "SELECT 1", llm_client=llm, mcp_client=_fake_mcp(),
        llm_settings=LLM_SETTINGS,
    )

    assert result["query_id"] == "q07"
    assert result["status"] == "parse_failed"
    assert result["error"]["code"] == "PARSE_FAILED"
    assert "proposals" not in result
    assert llm.messages.create.await_count == 3
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "parse_failed"
    assert re.fullmatch(r"[0-9a-f]{64}", record["response_sha256"])
    assert "không phải JSON" not in json.dumps(record, ensure_ascii=False)


@pytest.mark.asyncio
async def test_agent_rejects_status_field_from_llm(run_log_dir):
    """LLM không được tự gắn trạng thái thành công/thất bại cho run."""
    answer = {
        "query_id": "q07", "diagnosis": "Không cần đổi", "proposals": [],
        "confidence": "low", "status": "parse_failed",
    }

    result = await analyze_query(
        "q07", "SELECT 1", llm_client=_fake_llm(json.dumps(answer)),
        mcp_client=_fake_mcp(), llm_settings=LLM_SETTINGS,
    )

    assert result["status"] == "parse_failed"
    assert "proposals" not in result
    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "parse_failed"


@pytest.mark.asyncio
async def test_agent_rejects_retry_limit_above_contract():
    """Cấu hình không được cho retry quá hai lần theo contract."""
    llm = _fake_llm("{}")

    with pytest.raises(ValueError, match="json_retry"):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=_fake_mcp(),
            llm_settings=LLM_SETTINGS | {"json_retry": 3},
        )

    llm.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_loads_project_settings_when_caller_omits_them():
    """Caller không phải tự chép model và giới hạn từ YAML vào dict."""
    answer = {"query_id": "q07", "diagnosis": "Không cần đổi", "proposals": [], "confidence": "low"}
    llm = _fake_llm(json.dumps(answer))

    result = await analyze_query(
        "q07", "SELECT 1", llm_client=llm, mcp_client=_fake_mcp(),
    )

    assert result == answer
    request = llm.messages.create.call_args.kwargs
    assert request["model"] == "openai/gpt-oss-120b"
    assert request["max_tokens"] == 2000
    assert request["temperature"] == 0.0


@pytest.mark.asyncio
async def test_agent_records_safe_api_error_fields_without_payload(run_log_dir):
    """Lưu dấu hiệu HTTP 400, không lưu nội dung lỗi có thể chứa SQL."""
    class FakeBadRequestError(Exception):
        status_code = 400

        def __init__(self):
            self.body = {"error": {
                "type": "invalid_request_error",
                "code": "tool_use_failed",
                "message": "SQL_PRIVATE_VALUE",
                "failed_generation": {"attempted_arguments": "SQL_PRIVATE_VALUE"},
            }}

    llm = SimpleNamespace(messages=SimpleNamespace(
        create=AsyncMock(side_effect=FakeBadRequestError()),
    ))
    with pytest.raises(FakeBadRequestError):
        await analyze_query(
            "q07", "SELECT 1", llm_client=llm, mcp_client=_fake_mcp(),
            llm_settings=LLM_SETTINGS,
        )

    record = json.loads(next(run_log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["status"] == "error"
    assert record["http_status"] == 400
    assert record["api_error_type"] == "invalid_request_error"
    assert record["api_error_code"] == "tool_use_failed"
    assert record["failed_generation_present"] is True
    assert "SQL_PRIVATE_VALUE" not in json.dumps(record)
