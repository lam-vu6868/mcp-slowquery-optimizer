"""
mcp_server/llm/agent.py
-----------------------

CHỨC NĂNG :
    Agent loop: gọi LLM qua client, cho phép Tool 1-5, nhận đề xuất cuối dạng JSON.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - CHỈ nạp danh sách Tool 1-5 cho LLM (không có apply_optimization).
    - Ghim model version, temperature thấp (0-0.2) để Consistency Rate có ý nghĩa; lấy từ config/settings.yaml.
    - Ghi metadata và hash của prompt/tool/kết quả vào data/outputs/runs/; không ghi SQL hoặc bí mật.
    - Có giới hạn số lượt tool call và ngân sách token mỗi query.

CẦN LÀM:
    [x] Vòng lặp tool-use (đã kiểm bằng client giả và thử q07 qua Groq/MCP/MySQL).
    [x] Retry khi JSON sai schema (tối đa 2 lần; đã kiểm bằng client giả).
    [x] Ghi metadata/hash lần chạy (đã kiểm bằng client giả).
    [x] Adapter Groq đã có; q07 có bốn lượt kiểm tra lại thành công qua API + MCP/MySQL.

THAM KHẢO  : docs/api-contract.md (mục 2.3), config/settings.yaml

TRẠNG THÁI : ĐANG LÀM — q07 có các lượt parse thành công; chưa đo 30 query.
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mcp_server.llm.parsers import parse_llm_response
from mcp_server.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_analysis_prompt
from mcp_server.utils.config import load_llm_settings
from mcp_server.utils.sanitize import strip_sql_comments

ALLOWED_TOOL_NAMES = frozenset({
    "get_slow_queries", "get_schema", "get_table_stats",
    "explain_query", "benchmark_query",
})
DEFAULT_RUN_DIR = Path(__file__).resolve().parents[2] / "data" / "outputs" / "runs"


def _sha256(text: str) -> str:
    """Tạo dấu vân tay 64 ký tự hex; không lưu nội dung đầu vào."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    """Ghi thời gian run theo ISO 8601 UTC của contract."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_run_record(record: dict) -> None:
    """Ghi JSON qua file tạm rồi đổi tên để tránh bản ghi dở dang."""
    DEFAULT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    temporary = DEFAULT_RUN_DIR / f".{record['run_id']}.tmp"
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DEFAULT_RUN_DIR / f"{record['run_id']}.json")


async def _run_agent_loop(
    query_id: str,
    user_prompt: str,
    *,
    llm_client,
    mcp_client,
    llm_settings: dict,
    schema_data: dict | None = None,
    run_record: dict,
) -> dict:
    """Thực hiện hội thoại LLM/MCP; cập nhật hash vào bản ghi run."""
    tool_list = await mcp_client.list_tools()
    available = {
        tool.name: tool for tool in tool_list.tools
        if tool.name in ALLOWED_TOOL_NAMES
    }
    if set(available) != ALLOWED_TOOL_NAMES:
        raise RuntimeError("MCP chưa cung cấp đủ Tool 1–5")

    # Lọc tại host để Tool 6 không lọt vào danh sách gửi cho LLM.
    tools = [{
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema,
    } for tool in available.values()]
    max_tool_calls = llm_settings["max_tool_calls_per_query"]
    if type(max_tool_calls) is not int or max_tool_calls < 1:
        raise ValueError("max_tool_calls_per_query phải là số nguyên dương")
    max_retries = llm_settings["json_retry"]
    if type(max_retries) is not int or not 0 <= max_retries <= 2:
        raise ValueError("json_retry phải là số nguyên từ 0 đến 2")

    messages = [{"role": "user", "content": user_prompt}]
    tool_call_count = 0
    retry_count = 0
    while True:
        response = await llm_client.messages.create(
            model=llm_settings["model"],
            max_tokens=llm_settings["max_tokens"],
            temperature=llm_settings["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
        )
        if response.stop_reason == "end_turn":
            text = "".join(block.text for block in response.content if block.type == "text")
            run_record["response_sha256"] = _sha256(text)
            try:
                if not text:
                    raise ValueError("LLM không trả JSON")
                return parse_llm_response(text, query_id, schema_data)
            except (ValueError, TypeError) as exc:
                if retry_count == max_retries:
                    return {
                        "query_id": query_id,
                        "status": "parse_failed",
                        "error": {"code": "PARSE_FAILED", "message": str(exc)},
                    }
                retry_count += 1
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"JSON chưa hợp lệ: {exc}. Hãy trả lại đúng một JSON object theo schema, "
                        f"giữ query_id là {query_id}."
                    ),
                })
                continue
        if response.stop_reason != "tool_use":
            raise RuntimeError(f"LLM dừng trước câu trả lời cuối: {response.stop_reason}")

        uses = [block for block in response.content if block.type == "tool_use"]
        if not uses:
            raise RuntimeError("tool_use không có yêu cầu gọi tool")
        if tool_call_count + len(uses) > max_tool_calls:
            raise RuntimeError("Vượt giới hạn số lần gọi tool")
        # Kiểm tra cả batch trước khi chạy để một Tool 6 không lọt qua sau Tool 1–5.
        for use in uses:
            if use.name not in available:
                raise PermissionError(f"Tool không được phép: {use.name}")
            if not isinstance(use.input, dict):
                raise TypeError("Tham số gọi tool phải là JSON object")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for use in uses:
            arguments_json = json.dumps(use.input, sort_keys=True, separators=(",", ":"))
            tool_event = {
                "name": use.name,
                "arguments_sha256": _sha256(arguments_json),
            }
            run_record["tool_calls"].append(tool_event)
            result = await mcp_client.call_tool(use.name, use.input)
            content = "\n".join(
                block.text for block in result.content if block.type == "text"
            )
            if not content:
                raise RuntimeError(f"Tool {use.name} không trả nội dung text")
            tool_event["result_sha256"] = _sha256(content)
            tool_event["is_error"] = bool(result.is_error)
            if use.name == "get_schema" and not result.is_error:
                payload = json.loads(content)
                if payload.get("ok") is True and payload.get("meta", {}).get("truncated") is False:
                    # Tool 2 có thể được gọi nhiều lần cho các bảng khác nhau.
                    known_tables = {
                        table["name"]: table for table in schema_data["tables"]
                    } if schema_data else {}
                    for table in payload["data"]["tables"]:
                        known_tables[table["name"]] = table
                    schema_data = {"tables": list(known_tables.values())}

            tool_result = {"type": "tool_result", "tool_use_id": use.id, "content": content}
            if result.is_error:
                tool_result["is_error"] = True
            tool_results.append(tool_result)
        messages.append({"role": "user", "content": tool_results})
        tool_call_count += len(uses)


async def analyze_query(
    query_id: str,
    sql: str,
    *,
    llm_client,
    mcp_client,
    llm_settings: dict | None = None,
    schema_data: dict | None = None,
) -> dict:
    """Phân tích một query và ghi metadata/hash của run vào thư mục local."""
    if llm_settings is None:
        llm_settings = load_llm_settings()
    user_prompt = build_analysis_prompt(query_id, sql)
    record = {
        "run_id": uuid4().hex,
        "started_at": _utc_now(),
        "query_id": query_id,
        "prompt_version": PROMPT_VERSION,
        "model": llm_settings["model"],
        "temperature": llm_settings["temperature"],
        "max_tokens": llm_settings["max_tokens"],
        "max_tool_calls_per_query": llm_settings["max_tool_calls_per_query"],
        "json_retry": llm_settings["json_retry"],
        "sql_sha256": _sha256(strip_sql_comments(sql)),
        "prompt_sha256": _sha256(SYSTEM_PROMPT + "\n" + user_prompt),
        "tool_calls": [],
    }
    try:
        result = await _run_agent_loop(
            query_id, user_prompt, llm_client=llm_client, mcp_client=mcp_client,
            llm_settings=llm_settings, schema_data=schema_data, run_record=record,
        )
        # Trạng thái run do agent quyết định, không lấy trường thừa từ JSON LLM.
        record["status"] = "success" if "proposals" in result else "parse_failed"
        record["proposal_count"] = len(result["proposals"]) if "proposals" in result else 0
        return result
    except Exception as exc:
        record["status"] = "error"
        record["error_type"] = type(exc).__name__
        status = getattr(exc, "status_code", None)
        if type(status) is int and 400 <= status < 600:
            record["http_status"] = status
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                error = body.get("error", body)
                if isinstance(error, dict):
                    for field in ("type", "code"):
                        value = error.get(field)
                        if isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,64}", value):
                            record[f"api_error_{field}"] = value
                    record["failed_generation_present"] = error.get("failed_generation") is not None
        raise
    finally:
        record["finished_at"] = _utc_now()
        _write_run_record(record)
